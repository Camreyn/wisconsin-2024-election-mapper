import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { applyDiscovery, applyDiscoverySummary } from "./apply-source-discovery.mjs";
import { applyStateSourceProfile } from "./apply-state-source-profile.mjs";
import { runAddStatePipeline } from "./add-state-pipeline.mjs";
import { bootstrapStateSources } from "./bootstrap-state-sources.mjs";
import { discoverSources } from "./discover-state-sources.mjs";
import { validateStateConfigFile } from "./validate-state-config.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function writeJson(file, value) {
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

function tempFile(name) {
  return path.join(os.tmpdir(), `source-pipeline-${process.pid}-${name}`);
}

const tempFiles = [];

try {
  const ndReport = tempFile("nd-discovery.json");
  const ndConfig = tempFile("nd-config.json");
  const mvicReport = tempFile("mvic-discovery.json");
  const mvicConfig = tempFile("mvic-config.json");
  const bootstrapConfig = tempFile("zz-config.json");
  const bootstrapReport = tempFile("zz-discovery.json");
  const lifecycleConfig = tempFile("zy-config.json");
  const lifecycleReport = tempFile("zy-discovery.json");
  const barrierHtml = tempFile("barrier.html");
  const barrierConfig = tempFile("barrier-config.json");
  const paProfileConfig = tempFile("pa-profile-config.json");
  tempFiles.push(ndReport, ndConfig, mvicReport, mvicConfig, bootstrapConfig, bootstrapReport, lifecycleConfig, lifecycleReport, barrierHtml, barrierConfig, paProfileConfig);
  const ndHtmlFile = path.join(root, "data/nd-2024-voter-turnout-details.html");

  const ndDiscovery = await discoverSources({
    state: "ND",
    url: "https://results.sos.nd.gov/VoterTurnoutDetails.aspx",
    htmlFile: ndHtmlFile,
  });
  writeJson(ndReport, ndDiscovery);
  assert(ndDiscovery.forms.some((form) => form.hasViewState), "ND discovery should detect ASP.NET viewstate.");
  assert(
    ndDiscovery.postbacks.some((postback) => postback.target === "ctl00$MainContent$lnkbtnTurnoutExport"),
    "ND discovery should detect turnout export postback target.",
  );
  assert(
    ndDiscovery.likelyDownloads.some((item) => item.url === "https://results.sos.nd.gov/ResultsExport.aspx?"),
    "ND discovery should include ResultsExport.aspx as a likely download.",
  );

  const ndApplied = readJson(path.join(root, "data/state-configs/nd.json"));
  const ndApplyResult = applyDiscovery(ndApplied, ndDiscovery);
  const ndApplySummary = applyDiscoverySummary(ndApplyResult, {
    configPath: ndConfig,
    reportPath: ndReport,
    write: true,
  });
  writeJson(ndConfig, ndApplied);
  const ndExport = ndApplied.sources.find((source) => source.url === "https://results.sos.nd.gov/ResultsExport.aspx?");
  assert(ndApplySummary.status === "written", "ND apply summary should report written status.");
  assert(ndExport, "ND apply should append ResultsExport.aspx candidate source.");
  assert(ndExport.discovery.status === "Needs postback parameters", "ND ResultsExport source should need postback parameters.");
  assert(
    ndExport.discovery.suggestedDownload?.type === "northDakotaResultsExport",
    "ND ResultsExport source should infer northDakotaResultsExport download type.",
  );
  assert(
    ndExport.discovery.suggestedParser?.certifiedResultsFormat === "northDakotaStatewideCsv",
    "ND ResultsExport source should infer northDakotaStatewideCsv parser hint.",
  );
  assert(ndExport.discovery.roleConfidence, "ND ResultsExport source should include role confidence.");
  assert(Array.isArray(ndExport.discovery.roleScores), "ND ResultsExport source should include role scores.");

  const bootstrapPreview = await bootstrapStateSources({
    state: "ZZ",
    name: "Pipeline Test",
    authority: "Pipeline Test Authority",
    url: "https://results.sos.nd.gov/VoterTurnoutDetails.aspx",
    htmlFile: ndHtmlFile,
    configPath: bootstrapConfig,
    reportPath: bootstrapReport,
  });
  assert(bootstrapPreview.summary.status === "preview", "Bootstrap preview should report preview status.");
  assert(bootstrapPreview.summary.scaffolded, "Bootstrap preview should scaffold a missing config in memory.");
  assert(!fs.existsSync(bootstrapConfig), "Bootstrap preview should not write a new config.");
  assert(!fs.existsSync(bootstrapReport), "Bootstrap preview should not write a discovery report.");

  const bootstrapWrite = await bootstrapStateSources({
    state: "ZZ",
    name: "Pipeline Test",
    authority: "Pipeline Test Authority",
    url: "https://results.sos.nd.gov/VoterTurnoutDetails.aspx",
    htmlFile: ndHtmlFile,
    configPath: bootstrapConfig,
    reportPath: bootstrapReport,
    write: true,
  });
  const writtenBootstrapConfig = readJson(bootstrapConfig);
  assert(bootstrapWrite.summary.status === "written", "Bootstrap write should report written status.");
  assert(bootstrapWrite.summary.reportWritten, "Bootstrap write should write the requested report.");
  assert(fs.existsSync(bootstrapReport), "Bootstrap write should create the discovery report.");
  assert(
    writtenBootstrapConfig.app.sourcePlan.discoveryCandidates.status === "Candidate",
    "Bootstrap write should add a Source Planner discovery candidate summary.",
  );
  assert(
    writtenBootstrapConfig.sources.some((source) => source.discovery?.suggestedDownload?.type === "northDakotaResultsExport"),
    "Bootstrap write should apply discovery inference to the scaffolded config.",
  );
  const bootstrapReadiness = validateStateConfigFile(bootstrapConfig);
  assert(bootstrapReadiness.status === "valid_with_gaps", "Bootstrap readiness should be valid but still report gaps.");
  assert(bootstrapReadiness.gaps.some((gap) => gap.code === "discovered-source-needs-review"), "Bootstrap readiness should flag discovered source review gaps.");
  assert(bootstrapReadiness.gaps.some((gap) => gap.capability === "certifiedResults"), "Bootstrap readiness should flag certified results readiness.");

  writeJson(mvicConfig, {
    code: "MI",
    name: "Michigan",
    sources: [],
    app: {
      sourcePlan: {},
      sourceInventory: [],
      checkedNotUsable: [],
    },
  });
  writeJson(mvicReport, {
    input: {
      url: "https://mvic.sos.state.mi.us/votehistory/Index?type=C&electionDate=11-5-2024",
    },
    likelyDownloads: [
      {
        type: "export-endpoint",
        url: "https://mvic.sos.state.mi.us/VoteHistory/GetElectionResultFile?electionId=699",
        source: "a",
        confidence: "medium",
        note: "",
      },
      {
        type: "export-endpoint",
        url: "https://mvic.sos.state.mi.us/VoteHistory/GetVoterTurnoutFile?electionId=699",
        source: "a",
        confidence: "medium",
        note: "",
      },
      {
        type: "export-endpoint",
        url: "https://mvic.sos.state.mi.us/VoteHistory/GetPrecinctResultsFile?electionId=699",
        source: "a",
        confidence: "medium",
        note: "",
      },
    ],
  });

  const mvicApplied = readJson(mvicConfig);
  applyDiscovery(mvicApplied, readJson(mvicReport));
  writeJson(mvicConfig, mvicApplied);
  const resultSource = mvicApplied.sources.find((source) => source.url.includes("GetElectionResultFile"));
  const turnoutSource = mvicApplied.sources.find((source) => source.url.includes("GetVoterTurnoutFile"));
  const precinctSource = mvicApplied.sources.find((source) => source.url.includes("GetPrecinctResultsFile"));
  assert(resultSource?.download?.type === "browserDownload", "MVIC result source should infer browserDownload.");
  assert(resultSource.localFile.endsWith(".txt"), "MVIC result source should infer .txt local file.");
  assert(
    resultSource.discovery.suggestedParser?.certifiedResultsFormat === "michiganCountyTab",
    "MVIC result source should infer michiganCountyTab parser hint.",
  );
  assert(turnoutSource?.discovery.role === "turnout", "MVIC turnout source should infer turnout role.");
  assert(precinctSource?.localFile.endsWith(".zip"), "MVIC precinct source should infer .zip local file.");
  assert(
    precinctSource?.discovery.suggestedParser?.reviewChartsFormat === "tabDelimitedZipComparison",
    "MVIC precinct source should infer tabDelimitedZipComparison parser hint.",
  );
  assert(resultSource.discovery.roleConfidence === "high", "MVIC result source should have high role confidence.");

  const lifecycle = await runAddStatePipeline({
    state: "ZY",
    name: "Lifecycle Test",
    authority: "Lifecycle Test Authority",
    url: "https://results.sos.nd.gov/VoterTurnoutDetails.aspx",
    htmlFile: ndHtmlFile,
    configPath: lifecycleConfig,
    reportPath: lifecycleReport,
    write: true,
    validate: true,
  });
  assert(lifecycle.status === "completed", "Lifecycle runner should complete scaffold/discovery/validation.");
  assert(fs.existsSync(lifecycleConfig), "Lifecycle runner should write the state config.");
  assert(fs.existsSync(lifecycleReport), "Lifecycle runner should write the discovery report.");
  assert(lifecycle.gitAddCommand.includes("git add"), "Lifecycle runner should emit a git add command.");
  assert(lifecycle.readiness.status === "valid_with_gaps", "Lifecycle runner should report valid_with_gaps for an unpromoted discovered state.");

  const paProfileSeed = {
    code: "PA",
    name: "Pennsylvania",
    authority: "Pennsylvania Department of State",
    electionYear: 2024,
    office: "President",
    output: {
      appDataFile: "data/pa-app-data.js",
      appDataGlobal: "PA_ELECTION_APP_DATA",
    },
    sources: [],
    app: {
      sourcePlan: {},
      sourceInventory: [],
      checkedNotUsable: [],
    },
  };
  const paProfileReport = {
    state: "PA",
    input: {
      url: "https://www.pa.gov/agencies/dos/resources/voting-and-elections-resources/voting-and-election-statistics/election-data",
    },
    page: {
      title: "Historical Elections Data | Department of State | Commonwealth of Pennsylvania",
    },
    resources: [
      {
        text: "Download the 2024 General Election Voter Registration Vote History",
        url: "https://www.pa.gov/content/dam/copapwp-pagov/en/dos/resources/voting-and-elections/bulk-data/2024-general-election/voter%20registration%20-%20vote%20history%20summary%20-%202024%20general.xlsx",
      },
      {
        text: "Download the 2024 General Voter Election Returns Precinct Data",
        url: "https://www.pa.gov/content/dam/copapwp-pagov/en/dos/resources/voting-and-elections/bulk-data/2024-general-election/er/erstat_2024_g_268768_20250129.txt",
      },
      {
        text: "Download the 2020 General Election Returns Precinct Data",
        url: "https://www.pa.gov/content/dam/copapwp-pagov/en/dos/resources/voting-and-elections/bulk-data/ElectionReturns_2020_General_PrecinctReturns.txt",
      },
      {
        text: "Download the 2016 General Election Returns Precinct Data",
        url: "https://www.pa.gov/content/dam/copapwp-pagov/en/dos/resources/voting-and-elections/bulk-data/ElectionReturns_2016_General_PrecinctReturns.txt",
      },
      {
        text: "Download the 2012 General Election Returns Precinct Data",
        url: "https://www.pa.gov/content/dam/copapwp-pagov/en/dos/resources/voting-and-elections/bulk-data/ElectionReturns_2012_General_PrecinctReturns.txt",
      },
    ],
  };
  const paProfile = applyStateSourceProfile(paProfileSeed, paProfileReport);
  writeJson(paProfileConfig, paProfileSeed);
  const paProfileReadiness = validateStateConfigFile(paProfileConfig);
  assert(paProfile.status === "applied", "PA source profile should apply to the official PA election data page.");
  assert(paProfileSeed.sources.some((source) => source.id === "pa-2024-vote-history-registration-summary"), "PA source profile should add the turnout workbook source.");
  assert(paProfileSeed.turnout.format === "pennsylvaniaVoteHistoryXlsx", "PA source profile should configure the turnout parser.");
  assert(paProfileSeed.historicalBaseline.format === "pennsylvaniaBulkCsv", "PA source profile should configure the historical parser.");
  assert(paProfileReadiness.status === "ready", "PA source profile should produce a ready config when source files already exist.");

  fs.writeFileSync(
    barrierHtml,
    '<html><head><script src="/_Incapsula_Resource?x=1"></script></head><body>Request unsuccessful. Incapsula incident ID: 123</body></html>',
    "utf8",
  );
  const barrierDiscovery = await discoverSources({
    state: "PX",
    url: "https://protected.example.test/results",
    htmlFile: barrierHtml,
  });
  assert(barrierDiscovery.accessBarrier.status === "blocked", "Access barrier discovery should detect blocked pages.");
  writeJson(barrierConfig, {
    code: "PX",
    name: "Protected Test",
    sources: [],
    app: {
      sourcePlan: {},
      sourceInventory: [],
      checkedNotUsable: [],
    },
  });
  const barrierApplied = readJson(barrierConfig);
  const barrierApply = applyDiscovery(barrierApplied, barrierDiscovery);
  assert(barrierApply.sourcePlanStatus === "Blocked by source protection", "Blocked discovery should set Source Planner blocked status.");
  assert(barrierApplied.app.checkedNotUsable.some((entry) => entry.status.includes("incapsula")), "Blocked discovery should add a checked follow-up entry.");

  console.log(JSON.stringify({
    status: "passed",
    nd: {
      likelyDownloads: ndDiscovery.likelyDownloads.length,
      postbacks: ndDiscovery.postbacks.length,
      appendedSources: ndApplySummary.addedSources.length,
      inferredDownload: ndExport.discovery.suggestedDownload.type,
    },
    bootstrap: {
      status: bootstrapWrite.summary.status,
      scaffolded: bootstrapWrite.summary.scaffolded,
      addedSources: bootstrapWrite.summary.apply.addedSources.length,
      readiness: bootstrapReadiness.status,
      readinessGaps: bootstrapReadiness.counts.gaps,
    },
    mvic: {
      appendedSources: mvicApplied.sources.length,
      resultDownload: resultSource.download.type,
      precinctParser: precinctSource.discovery.suggestedParser.reviewChartsFormat,
    },
    lifecycle: {
      status: lifecycle.status,
      readiness: lifecycle.readiness.status,
      filesToReview: lifecycle.filesToReview.length,
    },
    paProfile: {
      status: paProfile.status,
      sources: paProfileSeed.sources.length,
      readiness: paProfileReadiness.status,
    },
    accessBarrier: {
      status: barrierDiscovery.accessBarrier.status,
      type: barrierDiscovery.accessBarrier.type,
      sourcePlanStatus: barrierApply.sourcePlanStatus,
    },
  }, null, 2));
} finally {
  for (const file of tempFiles) {
    try {
      fs.rmSync(file, { force: true });
    } catch {
      // Temp cleanup is best effort.
    }
  }
}
