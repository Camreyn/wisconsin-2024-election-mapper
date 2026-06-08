(function () {

    "use strict";

    angular.module("EnrApp")
           .controller("MainController", ["$scope", "$rootScope", "$compile", "$timeout", "$window", "$filter", "jsonDataFetcher", "secondsCountdown", "enrModeManager", "primaryService", "$location",
    function ($scope, $rootScope, $compile, $timeout, $window, $filter, jsonDataFetcher, secondsCountdown, enrModeManager, primaryService, $location) {
        
        $scope.badgeClassD = "header-badge";
        $scope.badgeClassR = "header-badge";
        $scope.isShow = true;
        $scope.isTopBanner = false;
        $scope.showMap = true;
        $scope.showVoterStatistics = false;
        $scope.showDownloadResults = false;
        $scope.modelhidden = true;
        $scope.currentYear = new Date().getFullYear();

        $scope.isSplash = false;
                
        if (localStorage.getItem('isRefresh') != 'Y') {
            var isFirstLogin;
            if (localStorage.getItem("isFirstLogin") != "null" && localStorage.getItem("isFirstLogin") != "undefined" && localStorage.getItem("isFirstLogin") == "false")
                isFirstLogin = localStorage.getItem("isFirstLogin");
            localStorage.clear();
            if (!isFirstLogin)
                localStorage.setItem("isFirstLogin", isFirstLogin);
        }

        $scope.onPrimaryPartyChanged = function (partyCode) {
            //primaryService.resetSelectedOffice();
            //primaryService.resetselectedCounty();
            //primaryService.resetselectedGeometryObjProperties();
            //primaryService.resetselectedGeometryObjProperties;
            //primaryService.resetselectedGeometryEventPath();
            //primaryService.resetisAnyRegionSelected();
            //primaryService.resetselectedNavtab();
            $scope.PartyCode = partyCode;
            primaryService.setSelectedParty(partyCode);
        };

        function selectFromSplash(newMode) {
            $scope.isSplash = false;
            angular.element(document.querySelector("#divFooter")).show();
            angular.element(document.querySelector("#divInfoText")).show();
            angular.element(document.querySelector("#divLogoSection")).show();
            angular.element(document.querySelector("#noResultsVisible")).show();
            updatePageTitle(newMode);
        }

        function updatePageTitle(newMode) {
            var newTitle = "Indiana Election Results";
            if (newMode === enrModeManager.modeEnum.turnout) {
                newTitle += " - Voter Statistics";
            } else if (newMode === enrModeManager.modeEnum.downloadResults) {
                newTitle += " - Download Results";
            } else if (newMode === enrModeManager.modeEnum.offices) {
                newTitle += " - Offices";
            } else if (newMode === enrModeManager.modeEnum.referendums) {
                newTitle += " - Referendums";
            }
            $window.document.title = newTitle;
        }

        $scope.$on("SELECT_FROM_SPLASH", function (event, newMode) {
            selectFromSplash(newMode);
        })

        $scope.$on("SELECTED_PARTY_CHANGED", function (event, partyCode, isSplash) {

            $scope.badgeClassD = "header-badge";
            $scope.badgeClassR = "header-badge"; 

            if (isSplash) {
                selectFromSplash(enrModeManager.modeEnum.offices);
            }

            if (partyCode === "D") {
                $scope.badgeClassD += " selected";
            }
            else if (partyCode === "R") {
                $scope.badgeClassR += " selected";
            }

        });


        $scope.$on("COUNTY_MOUSEOVER_POSITION", function (event, modelhidden, modelTop, modelLeft) {
            $scope.modelhidden = modelhidden;
            $scope.modelTop = modelTop;
            $scope.modelLeft = modelLeft;
        });

        var isEnr = true;
        $scope.PartyCode = '';
        $scope.bindParams = function (parameters) {
            var isBannerVal = parameters[1].replace("/1.1", "");
            if (parameters[0] == "Type") {
                jsonDataFetcher.registerElectionType(parameters[1]);
            }
            else if (parameters[0] == "isTopBanner") {
                if (isBannerVal == 'Y') {
                    isEnr = false;
                }
            }
            else if (parameters[0] == "isShow") {
                if (isBannerVal == 'N') {
                    isEnr = false;
                }
            }
            else if (parameters[0] == "PartyCode") {
                $scope.PartyCode = isBannerVal;
            }
        }

        var params = $window.location.search;
        if (params) {

            if (params.indexOf("?") > -1) {
                if (params.indexOf("&") > -1) {
                    var mutiParams = params.substr(1, params.length).split("&");
                    for (var i = 0; i < mutiParams.length; i++) {
                        var parameters = mutiParams[i].split('=');
                        $scope.bindParams(parameters);
                    }
                }
                else {
                    var mutiParams = params.substr(1, params.length).split("=");
                    $scope.bindParams(mutiParams);
                }
            }
        }
                
        $scope.modelMouseEnter = function (event) {
            primaryService.setIsMouseArrivedOnModel(true);
        }

        $scope.modelMouseLeave = function (event) {
            primaryService.setIsMouseArrivedOnModel(false);
            $scope.modelhidden = true;
        }

        $scope.$on(enrModeManager.modeChangeEventName, function (event, newMode) {
            updatePageTitle(newMode);
            $scope.showOfficeList = newMode === enrModeManager.modeEnum.offices;
            $scope.showMap = false;
            $scope.showVoterStatistics = false;
            $scope.showDownloadResults = false;

            if (newMode === enrModeManager.modeEnum.turnout) {
                $scope.showVoterStatistics = true;
            } else if (newMode === enrModeManager.modeEnum.downloadResults) {
                $scope.showDownloadResults = true;
            } else if (newMode === enrModeManager.modeEnum.offices) {
                $scope.showMap = true;
            } else if (newMode === enrModeManager.modeEnum.referendums) {
                $scope.showMap = true;
                // State Constitutional Amendment
                jsonDataFetcher.fetchSingleJson("statewideElectionsR", true, false, function (jsonResults) {
                    var referendumsData = jsonResults;

                    var jurisdictionJsonFiles = [];
                    var areVersioned = [];
                    var areClientData = [];

                    if (referendumsData != undefined) {
                        if (referendumsData.Regions != undefined && referendumsData.Regions.Region != undefined) {
                            if (referendumsData.Regions.Region.length == undefined)
                                referendumsData.Regions.Region = [referendumsData.Regions.Region];

                            angular.forEach(referendumsData.Regions.Region, function (regionData) {
                                jurisdictionJsonFiles.push("JurR_" + regionData.FIPS);
                                areVersioned.push(true);
                                areClientData.push(false);
                            });

                            jsonDataFetcher.fetchMultipleJson(jurisdictionJsonFiles, areVersioned, areClientData, function (jsonResult) {
                                var positiveResults = 0;
                                var negativeResults = 0;
                                var stateReferendumObject = null;
                                var isStateConstReferendum = false;
                                angular.forEach(jsonResult, function (jurisdictionList) {
                                    if (jurisdictionList.length == undefined)
                                        jurisdictionList = [jurisdictionList];

                                    angular.forEach(jurisdictionList, function (jurisdiction) {
                                        if (jurisdiction.Region != undefined &&
                                            jurisdiction.Region.Reporting_Regions != undefined &&
                                            jurisdiction.Region.Reporting_Regions.Regions != undefined &&
                                            jurisdiction.Region.Reporting_Regions.Regions.Referendums != undefined &&
                                            jurisdiction.Region.Reporting_Regions.Regions.Referendums.Referendum != undefined) {
                                            var referendumArray = jurisdiction.Region.Reporting_Regions.Regions.Referendums.Referendum;
                                            if (referendumArray.length == undefined)
                                                referendumArray = [referendumArray];

                                            angular.forEach(referendumArray, function (referendumObject) {
                                                if (referendumObject.REFERENDUM_TYPE_NAME == "Ratification Of State Constitutional Amendment") {
                                                    isStateConstReferendum = true;
                                                    stateReferendumObject = referendumObject;
                                                    positiveResults += parseInt(referendumObject.POSITIVE_RESULTS);
                                                    negativeResults += parseInt(referendumObject.NEGATIVE_RESULTS);
                                                }
                                            });
                                        }
                                    });
                                });

                                if (isStateConstReferendum) {
                                    stateReferendumObject.POSITIVE_RESULTS = positiveResults;
                                    stateReferendumObject.NEGATIVE_RESULTS = negativeResults;
                                    primaryService.setStateConReferendum(stateReferendumObject);
                                }

                            });

                        }
                    }
                });
            }
        });

        // Start by pulling settings data (which will also give us version information)
        jsonDataFetcher.fetchSingleJson("settings", false, false, function (settingsJson) {
            jsonDataFetcher.registerVersion(settingsJson.VersionType);
            var isCertified = settingsJson.Certified === "T" ? true : false;
            primaryService.setIsCertified(isCertified);

            if (settingsJson.ElectionType === "P" && isEnr) {
                $scope.isSplash = true;
            } else {
                updatePageTitle(enrModeManager.modeEnum.offices);
            }

            if (!isEnr) {
                $rootScope.isEnrNav = true;
            }

            // Now that we know what our version is, pull the rest of the data we need on startup.
            jsonDataFetcher.fetchMultipleJson(["statewideElectionsC", "statewideTickerC", "additionalSettings", "statewideTickerR"], [true, true, false, true], [false, false, true, false], function (jsonResults) {

                var officeListJson = jsonResults[0];
                var tickerJson = jsonResults[1];
                var additionalSettings = jsonResults[2];
                var officesData = jsonResults[0].List;
                var tickerJsonR = jsonResults[3];

                var officeJsonFiles = [];
                var areVersioned = [];
                var areClientData = [];

                angular.forEach(officesData, function (office) {
                    var val = office;
                    if (office.Items != undefined) {
                        angular.forEach(office.Items.Item, function (officeItem) {
                            //$scope.currentOffices.push(officeItem);
                            officeJsonFiles.push("OffCatC_" + officeItem.OFFICECATEGORYID);
                            areVersioned.push(true);
                            areClientData.push(false);
                        });
                    }
                });

                primaryService.setOfficersJsonData(officeJsonFiles);

                jsonDataFetcher.fetchMultipleJson(officeJsonFiles, areVersioned, areClientData, function (jsonResult) {
                    primaryService.setOfficesList(jsonResult);
                    $rootScope.$broadcast("DEFAULT_OFFICE_CHANGE");
                });

                jsonDataFetcher.fetchSingleJson("mapDataIndianaDistricts", false, true, function (jsonResult) {
                    primaryService.setMapDistrictData(jsonResult);
                });

                $scope.ElectionDate = new Date(settingsJson.CurrentElection);
                $scope.VersionTimestamp = settingsJson.VersionCode;

                $scope.DefaultMap = settingsJson.DefaultMapName;
                $rootScope.DefaultMap = settingsJson.DefaultMapName;

                $scope.SpecialElectionColor = additionalSettings.AdditionalColors.SPECIAL_ELECTION_COLOR;

                settingsJson.PolParties.AdditionalColors = additionalSettings.AdditionalColors;

                $scope.PartyColor = {
                    Republican: null,
                    Democrat: null
                };

                var republicanResults = $filter('filter')(settingsJson.PolParties.PolParty, {
                    PARTY_NAME: "Republican"
                });
                if (republicanResults && republicanResults.length > 0)
                    $scope.PartyColor.Republican = republicanResults[0].DISPLAY_COLOR
                var democratResults = $filter('filter')(settingsJson.PolParties.PolParty, {
                    PARTY_NAME: "Democrat"
                });
                if (democratResults && democratResults.length > 0)
                    $scope.PartyColor.Democrat = democratResults[0].DISPLAY_COLOR

                $scope.MapColorsData = settingsJson.PolParties;
                $scope.MapColorsData.PartyColor = $scope.PartyColor;
                $scope.MapGeoData = undefined;

                $scope.ReportingMeterValue = officeListJson.JurisdictionsReporting.TOTAL_ALLPRECINCTSREPORTING / officeListJson.JurisdictionsReporting.TOTAL_ALLPRECINCTS;
                $scope.PercentReporting = $filter("percentage")($scope.ReportingMeterValue, 1);
                $scope.TotalPrecincts = officeListJson.JurisdictionsReporting.TOTAL_ALLPRECINCTS;

                var initialSecondsTillRefresh = settingsJson.IntervalInMinutes * 60;

                if ((new Date() - new Date(settingsJson.CurrentElection)) > 1166400000) {
                    initialSecondsTillRefresh = 30 * 60;
                }

                secondsCountdown.start(initialSecondsTillRefresh, function () {                    
                    localStorage.setItem("isRefresh", "Y");
                    localStorage.setItem("partyCode", primaryService.getSelectedParty());
                    localStorage.setItem("OfficeCode", JSON.stringify(primaryService.getSelectedOffice()));
                    localStorage.setItem("CountyCode", JSON.stringify(primaryService.getSelectedCounty()));
                    localStorage.setItem("GeometryObjProperties", JSON.stringify(primaryService.getSelectedGeometryObjProperties()));
                    localStorage.setItem("GeometryEventPath", JSON.stringify(primaryService.getSelectedGeometryEventPath()));
                    localStorage.setItem("IsAnyRegionSelected", primaryService.getIsAnyRegionSelected());
                    localStorage.setItem("SelectedNavtab", primaryService.getSelectedNavtab());
                    localStorage.setItem("MainNavtab", enrModeManager.getCurMode());

                    $("#divStatus").html("Refreshing page...");
                    $window.location.reload();
                });
                $scope.SecondsTilRefresh = secondsCountdown.secondsRemaining;
                $scope.RefreshMeterValue = function () {
                    return 1 - ($scope.SecondsTilRefresh() / initialSecondsTillRefresh);
                };
                $scope.ToggleCountdownPause = function () {
                    secondsCountdown.togglePause();
                    $rootScope.$broadcast('timerPausedChanged', { isPaused: secondsCountdown.isPaused() });
                };

                $scope.OfficeListData = officeListJson;
                $scope.showOfficeList = true;
                $scope.IsPrimary = settingsJson.ElectionType === "P";
                primaryService.setElectionType(settingsJson.ElectionType);
                if (tickerJson.ElectionSummaries != undefined) {
                    $scope.TickerData = tickerJson.ElectionSummaries.Race;
                }

                if (typeof (tickerJsonR) != "undefined" && typeof (tickerJsonR.ElectionSummaries) != "undefined" && typeof (tickerJsonR.ElectionSummaries.Question) != "undefined") {
                    $scope.TickerDataR = tickerJsonR.ElectionSummaries.Question;
                }

                if (localStorage.getItem("isRefresh") == "Y") {

                    primaryService.setSelectedParty(localStorage.getItem("partyCode"), true);
                    primaryService.setSelectedOffice(JSON.parse(localStorage.getItem("OfficeCode") == 'undefined' ? null : localStorage.getItem("OfficeCode")));
                    primaryService.setSelectedCounty(JSON.parse(localStorage.getItem("CountyCode") == 'undefined' ? null : localStorage.getItem("CountyCode")));
                    primaryService.setSelectedGeometryObjProperties(JSON.parse(localStorage.getItem("GeometryObjProperties") == 'undefined' ? null : localStorage.getItem("GeometryObjProperties")));
                    primaryService.setSelectedGeometryEventPath(JSON.parse(localStorage.getItem("GeometryEventPath") == 'undefined' ? null : localStorage.getItem("GeometryEventPath")));
                    primaryService.setIsAnyRegionSelected((localStorage.getItem("IsAnyRegionSelected")));
                    primaryService.setSelectedNavtab((localStorage.getItem("SelectedNavtab")));
                    enrModeManager.setCurMode(localStorage.getItem("MainNavtab") == 'undefined' ? null : parseInt(localStorage.getItem("MainNavtab")));

                    localStorage.setItem("isRefresh", "N");
                    $scope.isSplash = false;
                    $scope.isShow = true;
                }

                if ($scope.IsPrimary) {
                    // We default to Democrats because that's alphabetical order.
                    if (((localStorage.getItem("partyCode") != "null" &&
                        localStorage.getItem("partyCode") != "undefined" &&
                        localStorage.getItem("partyCode") != null))) {
                        if (((localStorage.getItem("partyCode").length > 0))) {
                            primaryService.setIsPrimary(true, ((localStorage.getItem("partyCode"))));
                        }
                    } else {
                        if ($scope.PartyCode != null && $scope.PartyCode === "2") {
                            enrModeManager.setCurMode(enrModeManager.modeEnum.referendums);
                        } else {
                            var SelectPartyCode = $scope.PartyCode;
                            if (SelectPartyCode && SelectPartyCode.length > 0)
                                primaryService.setIsPrimary(true, SelectPartyCode);
                            else
                                primaryService.setIsPrimary(true, "D");
                        }
                    }
                } else {
                    if ($scope.PartyCode != null) {
                        if ($scope.PartyCode === "2") {
                            enrModeManager.setCurMode(enrModeManager.modeEnum.referendums);
                        } else if ($scope.PartyCode === "1") {
                            enrModeManager.setCurMode(enrModeManager.modeEnum.offices);
                        }
                    }
                }

                primaryService.setPartyColors($scope.PartyColor);

                $scope.stopInterval = function () {
                    secondsCountdown.stopInterval();
                }
                $scope.electionType = primaryService.getElectionType();

                $scope.bindBannerParams = function (parameters) {

                    var isBannerVal = parameters[1].replace("/1.1", "");

                    if (parameters[0] == "isTopBanner") {
                        if (isBannerVal == 'N') {
                            $scope.stopInterval();
                            $scope.isShow = false;
                        }
                        else if (isBannerVal == 'Y') {
                            $scope.stopInterval();
                            $scope.isTopBanner = true;
                        }
                    }
                    else if (parameters[0] == "isShow") {
                        if (isBannerVal == 'N') {
                            $scope.stopInterval();
                            $scope.isShow = false;
                        }
                    }
                    else if (parameters[0] == "year") {
                        if (isBannerVal == '2016') {
                            if ($scope.electionType == 'G')
                                $scope.electionResultsDocument = "Content/documents/2024 General Election More Information Document _Final.pdf";
                            else
                                $scope.electionResultsDocument = "Content/documents/2024 General Election More Information Document _Final.pdf";
                        }
                    }
                }

                var paramsBanner = $window.location.search;
                if (paramsBanner) {

                    if (paramsBanner.indexOf("?") > -1) {
                        if (paramsBanner.indexOf("&") > -1) {
                            var mutiParams = paramsBanner.substr(1, paramsBanner.length).split("&");
                            for (var i = 0; i < mutiParams.length; i++) {
                                var parameters = mutiParams[i].split('=');
                                $scope.bindBannerParams(parameters);
                            }
                        }
                        else {
                            var mutiParams = paramsBanner.substr(1, paramsBanner.length).split("=");
                            $scope.bindBannerParams(mutiParams);
                        }
                    }
                }

                if ($scope.isShow) {
                    if ($scope.electionType == 'G') {
                        $scope.spanElectionType = 'general';
                        $scope.electionResultsDocument = "Content/documents/2024 General Election More Information Document _Final.pdf";
                    }
                    else {
                        $scope.spanElectionType = 'primary';
                        $scope.electionResultsDocument = "Content/documents/2024 General Election More Information Document _Final.pdf";
                    }
                }
            });
        });        
    }]);
}());

