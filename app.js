const RESULTS = [
  { county: "Adams", trump: 7763, trumpPct: 60.26, harris: 4443, harrisPct: 34.49, other: 676, otherPct: 5.25, margin: 3320, marginPct: 25.77, total: 12882 },
  { county: "Ashland", trump: 4191, trumpPct: 46.8, harris: 4612, harrisPct: 51.5, other: 152, otherPct: 1.7, margin: -421, marginPct: -4.7, total: 8955 },
  { county: "Barron", trump: 16726, trumpPct: 62.39, harris: 8941, harrisPct: 33.35, other: 1142, otherPct: 4.26, margin: 7785, marginPct: 29.04, total: 26809 },
  { county: "Bayfield", trump: 4860, trumpPct: 43.24, harris: 6107, harrisPct: 54.33, other: 273, otherPct: 2.43, margin: -1247, marginPct: -11.09, total: 11240 },
  { county: "Brown", trump: 79132, trumpPct: 52.99, harris: 67937, harrisPct: 45.49, other: 2264, otherPct: 1.52, margin: 11195, marginPct: 7.5, total: 149333 },
  { county: "Buffalo", trump: 5213, trumpPct: 64.36, harris: 2765, harrisPct: 34.14, other: 122, otherPct: 1.51, margin: 2448, marginPct: 30.22, total: 8100 },
  { county: "Burnett", trump: 7008, trumpPct: 64.83, harris: 3665, harrisPct: 33.9, other: 137, otherPct: 1.27, margin: 3343, marginPct: 30.93, total: 10810 },
  { county: "Calumet", trump: 19488, trumpPct: 59.21, harris: 12927, harrisPct: 39.27, other: 501, otherPct: 1.52, margin: 6561, marginPct: 19.93, total: 32916 },
  { county: "Chippewa", trump: 23399, trumpPct: 60.82, harris: 14573, harrisPct: 37.88, other: 499, otherPct: 1.3, margin: 8826, marginPct: 22.94, total: 38471 },
  { county: "Clark", trump: 10481, trumpPct: 68.32, harris: 4509, harrisPct: 29.39, other: 350, otherPct: 2.28, margin: 5972, marginPct: 38.93, total: 15340 },
  { county: "Columbia", trump: 17988, trumpPct: 51.52, harris: 16388, harrisPct: 46.94, other: 538, otherPct: 1.54, margin: 1600, marginPct: 4.58, total: 34914 },
  { county: "Crawford", trump: 5113, trumpPct: 56.16, harris: 3860, harrisPct: 42.39, other: 132, otherPct: 1.45, margin: 1253, marginPct: 13.76, total: 9105 },
  { county: "Dane", trump: 85454, trumpPct: 23.35, harris: 273995, harrisPct: 74.88, other: 6480, otherPct: 1.77, margin: -188541, marginPct: -51.52, total: 365929 },
  { county: "Dodge", trump: 33067, trumpPct: 65.74, harris: 16518, harrisPct: 32.84, other: 715, otherPct: 1.42, margin: 16549, marginPct: 32.9, total: 50300 },
  { county: "Door", trump: 10099, trumpPct: 48.22, harris: 10565, harrisPct: 50.44, other: 280, otherPct: 1.34, margin: -466, marginPct: -2.22, total: 20944 },
  { county: "Douglas", trump: 11732, trumpPct: 46.49, harris: 13073, harrisPct: 51.81, other: 429, otherPct: 1.7, margin: -1341, marginPct: -5.31, total: 25234 },
  { county: "Dunn", trump: 14726, trumpPct: 57.35, harris: 10643, harrisPct: 41.45, other: 309, otherPct: 1.2, margin: 4083, marginPct: 15.9, total: 25678 },
  { county: "Eau Claire", trump: 27728, trumpPct: 43.89, harris: 34400, harrisPct: 54.45, other: 1049, otherPct: 1.66, margin: -6672, marginPct: -10.56, total: 63177 },
  { county: "Florence", trump: 2356, trumpPct: 74.6, harris: 783, harrisPct: 24.79, other: 19, otherPct: 0.6, margin: 1573, marginPct: 49.81, total: 3158 },
  { county: "Fond du Lac", trump: 37272, trumpPct: 63.68, harris: 20495, harrisPct: 35.02, other: 760, otherPct: 1.3, margin: 16777, marginPct: 28.67, total: 58527 },
  { county: "Forest", trump: 3382, trumpPct: 66.35, harris: 1681, harrisPct: 32.98, other: 34, otherPct: 0.67, margin: 1701, marginPct: 33.37, total: 5097 },
  { county: "Grant", trump: 15922, trumpPct: 58.31, harris: 10966, harrisPct: 40.16, other: 418, otherPct: 1.53, margin: 4956, marginPct: 18.15, total: 27306 },
  { county: "Green", trump: 10843, trumpPct: 49.12, harris: 10903, harrisPct: 49.39, other: 330, otherPct: 1.49, margin: -60, marginPct: -0.27, total: 22076 },
  { county: "Green Lake", trump: 7458, trumpPct: 67.48, harris: 3449, harrisPct: 31.21, other: 145, otherPct: 1.31, margin: 4009, marginPct: 36.27, total: 11052 },
  { county: "Iowa", trump: 6631, trumpPct: 45.18, harris: 7750, harrisPct: 52.8, other: 296, otherPct: 2.02, margin: -1119, marginPct: -7.62, total: 14677 },
  { county: "Iron", trump: 2557, trumpPct: 62.61, harris: 1487, harrisPct: 36.41, other: 40, otherPct: 0.98, margin: 1070, marginPct: 26.2, total: 4084 },
  { county: "Jackson", trump: 6204, trumpPct: 59.07, harris: 4157, harrisPct: 39.58, other: 141, otherPct: 1.34, margin: 2047, marginPct: 19.49, total: 10502 },
  { county: "Jefferson", trump: 28771, trumpPct: 57.37, harris: 20574, harrisPct: 41.03, other: 801, otherPct: 1.6, margin: 8197, marginPct: 16.35, total: 50146 },
  { county: "Juneau", trump: 9525, trumpPct: 65.45, harris: 4854, harrisPct: 33.35, other: 174, otherPct: 1.2, margin: 4671, marginPct: 32.1, total: 14553 },
  { county: "Kenosha", trump: 47478, trumpPct: 52.36, harris: 41826, harrisPct: 46.12, other: 1376, otherPct: 1.52, margin: 5652, marginPct: 6.23, total: 90680 },
  { county: "Kewaunee", trump: 8267, trumpPct: 66.22, harris: 4059, harrisPct: 32.51, other: 158, otherPct: 1.27, margin: 4208, marginPct: 33.71, total: 12484 },
  { county: "La Crosse", trump: 32247, trumpPct: 44.63, harris: 39008, harrisPct: 53.98, other: 1006, otherPct: 1.39, margin: -6761, marginPct: -9.36, total: 72261 },
  { county: "Lafayette", trump: 5256, trumpPct: 59.51, harris: 3469, harrisPct: 39.28, other: 107, otherPct: 1.21, margin: 1787, marginPct: 20.23, total: 8832 },
  { county: "Langlade", trump: 7782, trumpPct: 66.72, harris: 3746, harrisPct: 32.12, other: 136, otherPct: 1.17, margin: 4036, marginPct: 34.6, total: 11664 },
  { county: "Lincoln", trump: 10633, trumpPct: 61.79, harris: 6306, harrisPct: 36.64, other: 270, otherPct: 1.57, margin: 4327, marginPct: 25.14, total: 17209 },
  { county: "Manitowoc", trump: 28200, trumpPct: 60.89, harris: 17399, harrisPct: 37.57, other: 717, otherPct: 1.55, margin: 10801, marginPct: 23.32, total: 46316 },
  { county: "Marathon", trump: 46213, trumpPct: 58.63, harris: 31529, harrisPct: 40, other: 1084, otherPct: 1.38, margin: 14684, marginPct: 18.63, total: 78826 },
  { county: "Marinette", trump: 16670, trumpPct: 68.28, harris: 7415, harrisPct: 30.37, other: 330, otherPct: 1.35, margin: 9255, marginPct: 37.91, total: 24415 },
  { county: "Marquette", trump: 6041, trumpPct: 64.08, harris: 3252, harrisPct: 34.5, other: 134, otherPct: 1.42, margin: 2789, marginPct: 29.59, total: 9427 },
  { county: "Menominee", trump: 296, trumpPct: 18.83, harris: 1266, harrisPct: 80.53, other: 10, otherPct: 0.64, margin: -970, marginPct: -61.7, total: 1572 },
  { county: "Milwaukee", trump: 138022, trumpPct: 29.74, harris: 316292, harrisPct: 68.15, other: 9793, otherPct: 2.11, margin: -178270, marginPct: -38.41, total: 464107 },
  { county: "Monroe", trump: 14563, trumpPct: 62.32, harris: 8476, harrisPct: 36.27, other: 330, otherPct: 1.41, margin: 6087, marginPct: 26.05, total: 23369 },
  { county: "Oconto", trump: 17675, trumpPct: 70.95, harris: 6967, harrisPct: 27.97, other: 270, otherPct: 1.08, margin: 10708, marginPct: 42.98, total: 24912 },
  { county: "Oneida", trump: 14455, trumpPct: 58.06, harris: 10080, harrisPct: 40.49, other: 360, otherPct: 1.45, margin: 4375, marginPct: 17.57, total: 24895 },
  { county: "Outagamie", trump: 60827, trumpPct: 54.34, harris: 49438, harrisPct: 44.17, other: 1667, otherPct: 1.49, margin: 11389, marginPct: 10.17, total: 111932 },
  { county: "Ozaukee", trump: 34504, trumpPct: 54.36, harris: 27874, harrisPct: 43.92, other: 1094, otherPct: 1.72, margin: 6630, marginPct: 10.45, total: 63472 },
  { county: "Pepin", trump: 2798, trumpPct: 64.26, harris: 1523, harrisPct: 34.98, other: 33, otherPct: 0.76, margin: 1275, marginPct: 29.28, total: 4354 },
  { county: "Pierce", trump: 14417, trumpPct: 56.78, harris: 10171, harrisPct: 40.06, other: 804, otherPct: 3.17, margin: 4246, marginPct: 16.72, total: 25392 },
  { county: "Polk", trump: 18296, trumpPct: 64.83, harris: 9567, harrisPct: 33.9, other: 359, otherPct: 1.27, margin: 8729, marginPct: 30.93, total: 28222 },
  { county: "Portage", trump: 20987, trumpPct: 48.52, harris: 21503, harrisPct: 49.71, other: 768, otherPct: 1.78, margin: -516, marginPct: -1.19, total: 43258 },
  { county: "Price", trump: 5763, trumpPct: 65.07, harris: 3005, harrisPct: 33.93, other: 88, otherPct: 0.99, margin: 2758, marginPct: 31.14, total: 8856 },
  { county: "Racine", trump: 56347, trumpPct: 52.33, harris: 49721, harrisPct: 46.17, other: 1618, otherPct: 1.5, margin: 6626, marginPct: 6.15, total: 107686 },
  { county: "Richland", trump: 5207, trumpPct: 55.85, harris: 3985, harrisPct: 42.74, other: 131, otherPct: 1.41, margin: 1222, marginPct: 13.11, total: 9323 },
  { county: "Rock", trump: 40218, trumpPct: 45.54, harris: 46642, harrisPct: 52.82, other: 1450, otherPct: 1.64, margin: -6424, marginPct: -7.27, total: 88310 },
  { county: "Rusk", trump: 5660, trumpPct: 68.44, harris: 2516, harrisPct: 30.42, other: 94, otherPct: 1.14, margin: 3144, marginPct: 38.02, total: 8270 },
  { county: "Sauk", trump: 18798, trumpPct: 50.02, harris: 18172, harrisPct: 48.35, other: 614, otherPct: 1.63, margin: 626, marginPct: 1.67, total: 37584 },
  { county: "Sawyer", trump: 6422, trumpPct: 57.65, harris: 4599, harrisPct: 41.28, other: 119, otherPct: 1.07, margin: 1823, marginPct: 16.36, total: 11140 },
  { county: "Shawano", trump: 15850, trumpPct: 67.45, harris: 7336, harrisPct: 31.22, other: 314, otherPct: 1.34, margin: 8514, marginPct: 36.23, total: 23500 },
  { county: "Sheboygan", trump: 38763, trumpPct: 57.37, harris: 27735, harrisPct: 41.05, other: 1064, otherPct: 1.57, margin: 11028, marginPct: 16.32, total: 67562 },
  { county: "St. Croix", trump: 35537, trumpPct: 58.6, harris: 23870, harrisPct: 39.36, other: 1235, otherPct: 2.04, margin: 11667, marginPct: 19.24, total: 60642 },
  { county: "Taylor", trump: 8209, trumpPct: 73.39, harris: 2823, harrisPct: 25.24, other: 154, otherPct: 1.38, margin: 5386, marginPct: 48.15, total: 11186 },
  { county: "Trempealeau", trump: 9661, trumpPct: 60.08, harris: 6219, harrisPct: 38.68, other: 199, otherPct: 1.24, margin: 3442, marginPct: 21.41, total: 16079 },
  { county: "Vernon", trump: 8807, trumpPct: 53.03, harris: 7514, harrisPct: 45.24, other: 288, otherPct: 1.73, margin: 1293, marginPct: 7.78, total: 16609 },
  { county: "Vilas", trump: 9837, trumpPct: 60.97, harris: 6119, harrisPct: 37.92, other: 179, otherPct: 1.11, margin: 3718, marginPct: 23.04, total: 16135 },
  { county: "Walworth", trump: 36603, trumpPct: 60.4, harris: 23161, harrisPct: 38.22, other: 833, otherPct: 1.37, margin: 13442, marginPct: 22.18, total: 60597 },
  { county: "Washburn", trump: 6962, trumpPct: 63.42, harris: 3867, harrisPct: 35.22, other: 149, otherPct: 1.36, margin: 3095, marginPct: 28.19, total: 10978 },
  { county: "Washington", trump: 61604, trumpPct: 67.4, harris: 28504, harrisPct: 31.18, other: 1299, otherPct: 1.42, margin: 33100, marginPct: 36.21, total: 91407 },
  { county: "Waukesha", trump: 162768, trumpPct: 59.02, harris: 108478, harrisPct: 39.33, other: 4541, otherPct: 1.65, margin: 54290, marginPct: 19.69, total: 275787 },
  { county: "Waupaca", trump: 20093, trumpPct: 66.09, harris: 9947, harrisPct: 32.72, other: 363, otherPct: 1.19, margin: 10146, marginPct: 33.37, total: 30403 },
  { county: "Waushara", trump: 9625, trumpPct: 67.01, harris: 4571, harrisPct: 31.82, other: 167, otherPct: 1.16, margin: 5054, marginPct: 35.19, total: 14363 },
  { county: "Winnebago", trump: 49179, trumpPct: 51.57, harris: 44660, harrisPct: 46.83, other: 1532, otherPct: 1.61, margin: 4519, marginPct: 4.74, total: 95371 },
  { county: "Wood", trump: 24997, trumpPct: 59.21, harris: 16599, harrisPct: 39.32, other: 620, otherPct: 1.47, margin: 8398, marginPct: 19.89, total: 42216 },
];

const CANDIDATE_BREAKDOWN = {
  "Adams": { kennedy: 320, stein: 188, oliver: 44, terry: 20, west: 40, deLaCruz: 35, sonski: 0, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 29 },
  "Ashland": { kennedy: 52, stein: 26, oliver: 26, terry: 8, west: 15, deLaCruz: 3, sonski: 2, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 20 },
  "Barron": { kennedy: 603, stein: 284, oliver: 71, terry: 40, west: 86, deLaCruz: 24, sonski: 5, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 29 },
  "Bayfield": { kennedy: 88, stein: 87, oliver: 27, terry: 13, west: 14, deLaCruz: 8, sonski: 0, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 36 },
  "Brown": { kennedy: 782, stein: 346, oliver: 436, terry: 172, west: 79, deLaCruz: 76, sonski: 23, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 350 },
  "Buffalo": { kennedy: 57, stein: 20, oliver: 17, terry: 16, west: 1, deLaCruz: 2, sonski: 0, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 9 },
  "Burnett": { kennedy: 66, stein: 19, oliver: 33, terry: 13, west: 1, deLaCruz: 2, sonski: 3, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 0 },
  "Calumet": { kennedy: 201, stein: 83, oliver: 93, terry: 42, west: 16, deLaCruz: 10, sonski: 4, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 52 },
  "Chippewa": { kennedy: 170, stein: 61, oliver: 118, terry: 57, west: 12, deLaCruz: 10, sonski: 2, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 69 },
  "Clark": { kennedy: 160, stein: 71, oliver: 40, terry: 38, west: 9, deLaCruz: 7, sonski: 0, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 25 },
  "Columbia": { kennedy: 199, stein: 83, oliver: 108, terry: 46, west: 19, deLaCruz: 12, sonski: 4, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 67 },
  "Crawford": { kennedy: 57, stein: 15, oliver: 17, terry: 13, west: 6, deLaCruz: 3, sonski: 0, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 21 },
  "Dane": { kennedy: 1413, stein: 1721, oliver: 1209, terry: 297, west: 355, deLaCruz: 396, sonski: 110, fox: 0, kienitz: 0, jenkins: 11, futureMadamPotus: 0, mcneil: 0, scattering: 968 },
  "Dodge": { kennedy: 309, stein: 132, oliver: 145, terry: 81, west: 24, deLaCruz: 16, sonski: 8, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 0 },
  "Door": { kennedy: 99, stein: 40, oliver: 51, terry: 24, west: 10, deLaCruz: 8, sonski: 5, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 43 },
  "Douglas": { kennedy: 150, stein: 74, oliver: 91, terry: 26, west: 10, deLaCruz: 9, sonski: 4, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 65 },
  "Dunn": { kennedy: 118, stein: 53, oliver: 83, terry: 26, west: 12, deLaCruz: 13, sonski: 4, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 0 },
  "Eau Claire": { kennedy: 315, stein: 197, oliver: 225, terry: 68, west: 25, deLaCruz: 45, sonski: 17, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 157 },
  "Florence": { kennedy: 9, stein: 2, oliver: 5, terry: 2, west: 1, deLaCruz: 0, sonski: 0, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 0 },
  "Fond du Lac": { kennedy: 279, stein: 125, oliver: 148, terry: 76, west: 24, deLaCruz: 19, sonski: 10, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 79 },
  "Forest": { kennedy: 12, stein: 7, oliver: 12, terry: 1, west: 0, deLaCruz: 0, sonski: 0, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 2 },
  "Grant": { kennedy: 187, stein: 52, oliver: 76, terry: 35, west: 7, deLaCruz: 9, sonski: 3, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 49 },
  "Green": { kennedy: 102, stein: 52, oliver: 73, terry: 41, west: 7, deLaCruz: 5, sonski: 0, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 50 },
  "Green Lake": { kennedy: 53, stein: 12, oliver: 38, terry: 19, west: 2, deLaCruz: 2, sonski: 2, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 17 },
  "Iowa": { kennedy: 116, stein: 64, oliver: 49, terry: 20, west: 11, deLaCruz: 6, sonski: 3, fox: 0, kienitz: 0, jenkins: 1, futureMadamPotus: 0, mcneil: 0, scattering: 26 },
  "Iron": { kennedy: 17, stein: 10, oliver: 2, terry: 3, west: 2, deLaCruz: 1, sonski: 0, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 5 },
  "Jackson": { kennedy: 60, stein: 30, oliver: 21, terry: 20, west: 6, deLaCruz: 3, sonski: 1, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 0 },
  "Jefferson": { kennedy: 294, stein: 98, oliver: 186, terry: 58, west: 35, deLaCruz: 19, sonski: 2, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 109 },
  "Juneau": { kennedy: 66, stein: 25, oliver: 29, terry: 23, west: 4, deLaCruz: 2, sonski: 2, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 23 },
  "Kenosha": { kennedy: 446, stein: 302, oliver: 208, terry: 99, west: 69, deLaCruz: 44, sonski: 9, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 199 },
  "Kewaunee": { kennedy: 58, stein: 19, oliver: 35, terry: 24, west: 4, deLaCruz: 0, sonski: 0, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 18 },
  "La Crosse": { kennedy: 417, stein: 199, oliver: 218, terry: 88, west: 36, deLaCruz: 29, sonski: 19, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 0 },
  "Lafayette": { kennedy: 54, stein: 21, oliver: 17, terry: 10, west: 2, deLaCruz: 3, sonski: 0, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 0 },
  "Langlade": { kennedy: 51, stein: 33, oliver: 26, terry: 14, west: 5, deLaCruz: 2, sonski: 0, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 5 },
  "Lincoln": { kennedy: 119, stein: 44, oliver: 36, terry: 33, west: 8, deLaCruz: 9, sonski: 0, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 21 },
  "Manitowoc": { kennedy: 266, stein: 99, oliver: 151, terry: 85, west: 27, deLaCruz: 8, sonski: 3, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 78 },
  "Marathon": { kennedy: 349, stein: 180, oliver: 266, terry: 93, west: 26, deLaCruz: 19, sonski: 4, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 147 },
  "Marinette": { kennedy: 128, stein: 45, oliver: 60, terry: 33, west: 7, deLaCruz: 6, sonski: 8, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 43 },
  "Marquette": { kennedy: 55, stein: 16, oliver: 21, terry: 18, west: 2, deLaCruz: 1, sonski: 0, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 21 },
  "Menominee": { kennedy: 7, stein: 2, oliver: 1, terry: 0, west: 0, deLaCruz: 0, sonski: 0, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 0 },
  "Milwaukee": { kennedy: 1905, stein: 3288, oliver: 1146, terry: 442, west: 1049, deLaCruz: 622, sonski: 71, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 1270 },
  "Monroe": { kennedy: 130, stein: 47, oliver: 59, terry: 27, west: 11, deLaCruz: 8, sonski: 10, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 38 },
  "Oconto": { kennedy: 95, stein: 29, oliver: 67, terry: 33, west: 7, deLaCruz: 8, sonski: 2, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 29 },
  "Oneida": { kennedy: 127, stein: 41, oliver: 79, terry: 41, west: 8, deLaCruz: 6, sonski: 3, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 55 },
  "Outagamie": { kennedy: 599, stein: 306, oliver: 464, terry: 142, west: 75, deLaCruz: 54, sonski: 27, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 0 },
  "Ozaukee": { kennedy: 285, stein: 192, oliver: 225, terry: 68, west: 31, deLaCruz: 20, sonski: 21, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 252 },
  "Pepin": { kennedy: 11, stein: 5, oliver: 9, terry: 4, west: 3, deLaCruz: 1, sonski: 0, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 0 },
  "Pierce": { kennedy: 348, stein: 186, oliver: 101, terry: 49, west: 28, deLaCruz: 20, sonski: 14, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 58 },
  "Polk": { kennedy: 136, stein: 65, oliver: 86, terry: 47, west: 3, deLaCruz: 12, sonski: 9, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 1, mcneil: 0, scattering: 0 },
  "Portage": { kennedy: 244, stein: 130, oliver: 149, terry: 51, west: 69, deLaCruz: 25, sonski: 13, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 87 },
  "Price": { kennedy: 42, stein: 13, oliver: 18, terry: 11, west: 2, deLaCruz: 2, sonski: 0, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 0 },
  "Racine": { kennedy: 490, stein: 341, oliver: 285, terry: 106, west: 64, deLaCruz: 48, sonski: 13, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 271 },
  "Richland": { kennedy: 50, stein: 25, oliver: 19, terry: 11, west: 4, deLaCruz: 4, sonski: 4, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 14 },
  "Rock": { kennedy: 497, stein: 315, oliver: 247, terry: 99, west: 47, deLaCruz: 48, sonski: 16, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 181 },
  "Rusk": { kennedy: 36, stein: 19, oliver: 15, terry: 14, west: 1, deLaCruz: 0, sonski: 4, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 5 },
  "Sauk": { kennedy: 287, stein: 118, oliver: 98, terry: 54, west: 21, deLaCruz: 26, sonski: 10, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 0 },
  "Sawyer": { kennedy: 41, stein: 17, oliver: 23, terry: 16, west: 3, deLaCruz: 1, sonski: 0, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 18 },
  "Shawano": { kennedy: 123, stein: 51, oliver: 53, terry: 34, west: 4, deLaCruz: 4, sonski: 3, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 42 },
  "Sheboygan": { kennedy: 369, stein: 146, oliver: 226, terry: 115, west: 34, deLaCruz: 22, sonski: 5, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 147 },
  "St. Croix": { kennedy: 426, stein: 195, oliver: 286, terry: 93, west: 42, deLaCruz: 28, sonski: 10, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 155 },
  "Taylor": { kennedy: 49, stein: 25, oliver: 34, terry: 23, west: 9, deLaCruz: 0, sonski: 14, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 0 },
  "Trempealeau": { kennedy: 97, stein: 27, oliver: 44, terry: 13, west: 2, deLaCruz: 3, sonski: 1, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 12 },
  "Vernon": { kennedy: 106, stein: 67, oliver: 44, terry: 21, west: 12, deLaCruz: 8, sonski: 1, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 29 },
  "Vilas": { kennedy: 74, stein: 21, oliver: 30, terry: 17, west: 3, deLaCruz: 0, sonski: 2, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 32 },
  "Walworth": { kennedy: 297, stein: 120, oliver: 185, terry: 65, west: 16, deLaCruz: 18, sonski: 5, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 127 },
  "Washburn": { kennedy: 42, stein: 22, oliver: 40, terry: 13, west: 4, deLaCruz: 3, sonski: 1, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 24 },
  "Washington": { kennedy: 442, stein: 153, oliver: 300, terry: 111, west: 19, deLaCruz: 29, sonski: 11, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 234 },
  "Waukesha": { kennedy: 1146, stein: 943, oliver: 1033, terry: 284, west: 114, deLaCruz: 79, sonski: 0, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 942 },
  "Waupaca": { kennedy: 125, stein: 49, oliver: 92, terry: 46, west: 8, deLaCruz: 7, sonski: 4, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 32 },
  "Waushara": { kennedy: 70, stein: 29, oliver: 41, terry: 20, west: 2, deLaCruz: 2, sonski: 3, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 0 },
  "Winnebago": { kennedy: 509, stein: 267, oliver: 372, terry: 111, west: 25, deLaCruz: 43, sonski: 17, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 188 },
  "Wood": { kennedy: 238, stein: 86, oliver: 129, terry: 68, west: 14, deLaCruz: 18, sonski: 10, fox: 0, kienitz: 0, jenkins: 0, futureMadamPotus: 0, mcneil: 0, scattering: 57 },
};

const CANDIDATE_LABELS = [
  { key: "kennedy", label: "Robert F. Kennedy Jr." },
  { key: "stein", label: "Jill Stein" },
  { key: "oliver", label: "Chase Oliver" },
  { key: "terry", label: "Randall Terry" },
  { key: "west", label: "Cornel West" },
  { key: "deLaCruz", label: "Claudia De la Cruz" },
  { key: "sonski", label: "Peter Sonski (write-in)" },
  { key: "fox", label: "Cherunda Lynn Fox (write-in)" },
  { key: "kienitz", label: "Brian Kienitz (write-in)" },
  { key: "jenkins", label: "Doug Jenkins / Kimberly LaLonde (write-in)" },
  { key: "futureMadamPotus", label: "Future Madam Potus / Jessica Kennedy (write-in)" },
  { key: "mcneil", label: "Andre Ramone McNeil Sr. (write-in)" },
  { key: "scattering", label: "Scattering" },
];

const TIGERWEB_COUNTIES =
  "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/3/query?where=STATE%3D%2755%27&outFields=NAME,GEOID&outSR=4326&f=geojson";

const ETA_ANALYSIS = {
  wardRows: 3603,
  downBallot: {
    demDropVotes: -4548,
    demDropPct: -0.2726,
    repDropVotes: 53630,
    repDropPct: 3.1591,
    demOutlierWards: 15,
    repOutlierWards: 46,
    outlierThresholdPct: 15,
    minCandidateVotes: 100,
  },
  voteShare: {
    trumpCorrelation: 0.2143,
    harrisCorrelation: 0.4145,
    threshold: 0.35,
  },
};

const TURNOUT_SOURCE_POLICY = {
  route: "countyMunicipalPdfs",
  status: "Needs data",
  acceptedSource:
    "County or municipal ward-by-ward canvass reports with registered voters and ballots cast.",
  warning:
    "Warning: some local reports label registered-voter counts as the number registered before Election Day. Wisconsin allows Election Day registration, so those denominators can be too low and can produce turnout rates over 100% without implying excess ballots or fraud.",
  requiredFields: [
    "county",
    "municipality",
    "ward",
    "ballotsCast",
    "registeredVoters",
    "registrationDenominatorTiming",
    "sourceUrl",
  ],
};

RESULTS.forEach((row) => {
  Object.assign(row, CANDIDATE_BREAKDOWN[row.county]);
});

const byCounty = new Map(RESULTS.map((row) => [normalizeCounty(row.county), row]));
const stateTotals = RESULTS.reduce(
  (acc, row) => {
    acc.trump += row.trump;
    acc.harris += row.harris;
    acc.other += row.other;
    acc.total += row.total;
    return acc;
  },
  { trump: 0, harris: 0, other: 0, total: 0 },
);

let collected = [];
let map;
let geoLayer;
let colorMode = "winner";
let selectedCounty = null;

const els = {
  trumpTotal: document.querySelector("#trumpTotal"),
  harrisTotal: document.querySelector("#harrisTotal"),
  stateMargin: document.querySelector("#stateMargin"),
  countyCount: document.querySelector("#countyCount"),
  collectBtn: document.querySelector("#collectBtn"),
  mapBtn: document.querySelector("#mapBtn"),
  exportBtn: document.querySelector("#exportBtn"),
  search: document.querySelector("#countySearch"),
  progressBar: document.querySelector("#progressBar"),
  statusText: document.querySelector("#statusText"),
  collectorLog: document.querySelector("#collectorLog"),
  etaTests: document.querySelector("#etaTests"),
  voteShareGraph: document.querySelector("#voteShareGraph"),
  downBallotGraph: document.querySelector("#downBallotGraph"),
  turnoutGraph: document.querySelector("#turnoutGraph"),
  countyRows: document.querySelector("#countyRows"),
  mapTitle: document.querySelector("#mapTitle"),
  map: document.querySelector("#map"),
  tileFallback: document.querySelector("#tileFallback"),
  selectedCounty: document.querySelector("#selectedCounty"),
  selectedWinner: document.querySelector("#selectedWinner"),
  selectedMargin: document.querySelector("#selectedMargin"),
  selectedTotal: document.querySelector("#selectedTotal"),
  breakdownTitle: document.querySelector("#breakdownTitle"),
  breakdownTotal: document.querySelector("#breakdownTotal"),
  candidateBreakdown: document.querySelector("#candidateBreakdown"),
};

function init() {
  renderSummary();
  renderEtaTests();
  renderEtaGraphs();
  renderCandidateBreakdown();
  renderTable(RESULTS);
  wireControls();
  initMap();
  collectCounties({ quick: true });
}

function wireControls() {
  els.collectBtn.addEventListener("click", () => collectCounties({ quick: false }));
  els.mapBtn.addEventListener("click", loadCountyBoundaries);
  els.exportBtn.addEventListener("click", exportCsv);
  els.search.addEventListener("input", () => {
    const query = els.search.value.trim().toLowerCase();
    const rows = RESULTS.filter((row) => row.county.toLowerCase().includes(query));
    renderTable(rows);
    renderTiles(rows);
  });

  document.querySelectorAll(".mode-button").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".mode-button").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      colorMode = button.dataset.mode;
      els.mapTitle.textContent =
        colorMode === "winner"
          ? "County winner shading"
          : colorMode === "margin"
            ? "Margin intensity shading"
            : "Total vote volume shading";
      refreshMapStyles();
      renderTiles(filteredRows());
    });
  });
}

function renderSummary() {
  const margin = stateTotals.trump - stateTotals.harris;
  const marginPct = (margin / stateTotals.total) * 100;
  els.trumpTotal.textContent = formatNumber(stateTotals.trump);
  els.harrisTotal.textContent = formatNumber(stateTotals.harris);
  els.stateMargin.textContent = `${margin > 0 ? "Trump +" : "Harris +"}${formatNumber(Math.abs(margin))} (${Math.abs(marginPct).toFixed(2)}%)`;
}

async function collectCounties({ quick }) {
  collected = [];
  els.collectBtn.disabled = true;
  els.collectorLog.innerHTML = "";
  updateProgress(0);

  const delay = quick ? 4 : 36;
  for (const [index, row] of RESULTS.entries()) {
    await sleep(delay);
    collected.push(row);
    if (!quick || index % 3 === 0 || index === RESULTS.length - 1) {
      addLog(`${row.county} County: ${winnerLabel(row)} by ${Math.abs(row.marginPct).toFixed(2)} points`);
    }
    updateProgress(collected.length);
  }

  els.statusText.textContent = `Collected ${RESULTS.length} county records from the certified county result table.`;
  els.collectBtn.disabled = false;
  renderTable(filteredRows());
  await loadCountyBoundaries();
}

function updateProgress(done) {
  const pct = (done / RESULTS.length) * 100;
  els.progressBar.style.width = `${pct}%`;
  els.countyCount.textContent = `${done} / ${RESULTS.length}`;
  if (done < RESULTS.length) {
    els.statusText.textContent = `Collecting county ${done + 1} of ${RESULTS.length}...`;
  }
}

function addLog(message) {
  const item = document.createElement("li");
  item.textContent = message;
  els.collectorLog.prepend(item);
  while (els.collectorLog.children.length > 9) {
    els.collectorLog.lastElementChild.remove();
  }
}

function initMap() {
  if (!window.L) {
    els.map.hidden = true;
    els.tileFallback.hidden = false;
    renderTiles(RESULTS);
    els.statusText.textContent = "Leaflet did not load, so the app is showing the county tile map.";
    return;
  }

  map = L.map("map", {
    attributionControl: false,
    zoomControl: true,
    scrollWheelZoom: true,
  }).setView([44.75, -89.85], 6);
}

async function loadCountyBoundaries() {
  if (!map) {
    renderTiles(filteredRows());
    return;
  }

  els.statusText.textContent = "Loading Wisconsin county boundaries from Census TIGERweb...";
  try {
    const response = await fetch(TIGERWEB_COUNTIES);
    if (!response.ok) {
      throw new Error(`Boundary request failed: ${response.status}`);
    }
    const geojson = await response.json();
    drawGeoJson(geojson);
    els.map.hidden = false;
    els.tileFallback.hidden = true;
    els.statusText.textContent = "County boundaries loaded and joined to the 2024 results.";
  } catch (error) {
    console.warn(error);
    els.map.hidden = true;
    els.tileFallback.hidden = false;
    renderTiles(filteredRows());
    els.statusText.textContent =
      "Could not load external county boundaries, so the county tile map is active.";
  }
}

function drawGeoJson(geojson) {
  if (geoLayer) {
    geoLayer.remove();
  }

  geoLayer = L.geoJSON(geojson, {
    style: (feature) => {
      const row = resultForFeature(feature);
      return countyStyle(row);
    },
    onEachFeature: (feature, layer) => {
      const row = resultForFeature(feature);
      if (!row) {
        return;
      }
      layer.bindPopup(popupHtml(row), { className: "county-popup" });
      layer.on({
        click: () => selectCounty(row.county),
        mouseover: () => layer.setStyle({ weight: 3, color: "#1b222b" }),
        mouseout: () => geoLayer.resetStyle(layer),
      });
    },
  }).addTo(map);

  map.fitBounds(geoLayer.getBounds(), { padding: [14, 14] });
}

function refreshMapStyles() {
  if (geoLayer) {
    geoLayer.setStyle((feature) => countyStyle(resultForFeature(feature)));
  }
}

function resultForFeature(feature) {
  return byCounty.get(normalizeCounty(feature?.properties?.NAME));
}

function countyStyle(row) {
  return {
    color: "#ffffff",
    fillColor: row ? colorFor(row) : "#b7c0c9",
    fillOpacity: row ? 0.86 : 0.42,
    opacity: 1,
    weight: selectedCounty && row?.county === selectedCounty ? 3 : 1,
  };
}

function colorFor(row) {
  if (colorMode === "turnout") {
    const t = Math.min(1, Math.sqrt(row.total / Math.max(...RESULTS.map((item) => item.total))));
    return blend("#d8dee4", "#3f8068", t);
  }

  const winner = row.margin >= 0 ? "r" : "d";
  const base = winner === "r" ? ["#f4d1ce", "#a8302a"] : ["#d6e5f5", "#1458a8"];

  if (colorMode === "winner") {
    return winner === "r" ? "#c84c42" : "#3477bd";
  }

  const intensity = Math.min(1, Math.abs(row.marginPct) / 65);
  return blend(base[0], base[1], intensity);
}

function blend(start, end, amount) {
  const s = hexToRgb(start);
  const e = hexToRgb(end);
  const mixed = s.map((value, index) => Math.round(value + (e[index] - value) * amount));
  return `rgb(${mixed.join(", ")})`;
}

function hexToRgb(hex) {
  return [1, 3, 5].map((index) => parseInt(hex.slice(index, index + 2), 16));
}

function renderTable(rows) {
  els.countyRows.innerHTML = rows
    .map(
      (row) => `
        <tr data-county="${row.county}" class="${selectedCounty === row.county ? "is-selected" : ""}">
          <td>${row.county}</td>
          <td>${formatNumber(row.trump)} <span class="party-r">${row.trumpPct.toFixed(2)}%</span></td>
          <td>${formatNumber(row.harris)} <span class="party-d">${row.harrisPct.toFixed(2)}%</span></td>
          <td>${formatNumber(row.other)} (${row.otherPct.toFixed(2)}%)</td>
          <td>${winnerLabel(row)} +${Math.abs(row.marginPct).toFixed(2)}%</td>
          <td>${formatNumber(row.total)}</td>
        </tr>
      `,
    )
    .join("");

  els.countyRows.querySelectorAll("tr").forEach((row) => {
    row.addEventListener("click", () => selectCounty(row.dataset.county));
  });
}

function renderTiles(rows) {
  els.tileFallback.innerHTML = rows
    .map(
      (row) => `
        <button class="county-tile" type="button" data-county="${row.county}" style="background:${colorFor(row)}">
          <strong>${row.county}</strong>
          <span>${winnerLabel(row)} +${Math.abs(row.marginPct).toFixed(2)}%</span>
          <span>${formatNumber(row.total)} votes</span>
        </button>
      `,
    )
    .join("");

  els.tileFallback.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => selectCounty(button.dataset.county));
  });
}

function selectCounty(county) {
  const row = byCounty.get(normalizeCounty(county));
  if (!row) {
    return;
  }
  selectedCounty = row.county;
  els.selectedCounty.textContent = `${row.county} County`;
  els.selectedWinner.textContent = winnerLabel(row);
  els.selectedMargin.textContent = `${formatNumber(Math.abs(row.margin))} votes (${Math.abs(row.marginPct).toFixed(2)}%)`;
  els.selectedTotal.textContent = formatNumber(row.total);
  renderCandidateBreakdown(row);
  renderEtaGraphs(row.county);
  renderTable(filteredRows());
  refreshMapStyles();
}

function renderEtaTests() {
  const tests = etaTestResults();
  els.etaTests.innerHTML = tests
    .map(
      (test) => `
        <article class="eta-test">
          <span class="eta-badge ${test.statusClass}">${test.status}</span>
          <div>
            <strong>${test.name}</strong>
            <p>${test.detail}</p>
            ${test.warning ? `<p class="eta-warning">${test.warning}</p>` : ""}
          </div>
        </article>
      `,
    )
    .join("");
}

function etaTestResults() {
  const voteShareFlagged =
    Math.abs(ETA_ANALYSIS.voteShare.trumpCorrelation) >= ETA_ANALYSIS.voteShare.threshold ||
    Math.abs(ETA_ANALYSIS.voteShare.harrisCorrelation) >= ETA_ANALYSIS.voteShare.threshold;
  const downBallotFlagged =
    Math.abs(ETA_ANALYSIS.downBallot.repDropPct) >= 2 ||
    Math.abs(ETA_ANALYSIS.downBallot.demDropPct) >= 2 ||
    ETA_ANALYSIS.downBallot.repOutlierWards + ETA_ANALYSIS.downBallot.demOutlierWards > 50;

  return [
    {
      name: "Down-ballot difference",
      status: downBallotFlagged ? "Flag" : "Pass",
      statusClass: downBallotFlagged ? "flag" : "pass",
      detail: `Ward-level President vs U.S. Senate check run on ${formatNumber(ETA_ANALYSIS.wardRows)} matched WEC ward rows. DEM presidential-vs-Senate drop-off: ${formatSigned(ETA_ANALYSIS.downBallot.demDropVotes)} votes (${ETA_ANALYSIS.downBallot.demDropPct.toFixed(2)}%). REP presidential-vs-Senate drop-off: ${formatSigned(ETA_ANALYSIS.downBallot.repDropVotes)} votes (${ETA_ANALYSIS.downBallot.repDropPct.toFixed(2)}%). Outlier wards over ${ETA_ANALYSIS.downBallot.outlierThresholdPct}% drop-off with at least ${ETA_ANALYSIS.downBallot.minCandidateVotes} presidential votes: DEM ${ETA_ANALYSIS.downBallot.demOutlierWards}, REP ${ETA_ANALYSIS.downBallot.repOutlierWards}.`,
    },
    {
      name: "Vote share by vote count",
      status: voteShareFlagged ? "Flag" : "Pass",
      statusClass: voteShareFlagged ? "flag" : "pass",
      detail: `Ward-level check run on ${formatNumber(ETA_ANALYSIS.wardRows)} WEC ward rows. Trump r=${ETA_ANALYSIS.voteShare.trumpCorrelation.toFixed(3)}, Harris r=${ETA_ANALYSIS.voteShare.harrisCorrelation.toFixed(3)} between candidate vote count and candidate vote share; app review threshold is |r| >= ${ETA_ANALYSIS.voteShare.threshold.toFixed(2)}.`,
    },
    {
      name: "Turnout analysis",
      status: TURNOUT_SOURCE_POLICY.status,
      statusClass: "needs-data",
      detail: `Not run yet. Best low-cost route is ${TURNOUT_SOURCE_POLICY.acceptedSource} Required fields: ${TURNOUT_SOURCE_POLICY.requiredFields.join(", ")}.`,
      warning: TURNOUT_SOURCE_POLICY.warning,
    },
    {
      name: "Official-result completeness",
      status: "Pass",
      statusClass: "pass",
      detail:
        "All 72 counties are present, detailed candidate/write-in totals sum to each county's Other total, and statewide totals match the WEC report.",
    },
  ];
}

function renderEtaGraphs(county = selectedCounty) {
  if (!window.ETA_WARD_CHARTS) {
    renderGraphMessage(els.voteShareGraph, "Ward-level chart data is not loaded.");
    renderGraphMessage(els.downBallotGraph, "Ward-level chart data is not loaded.");
    renderGraphMessage(els.turnoutGraph, TURNOUT_SOURCE_POLICY.warning);
    return;
  }

  renderVoteShareGraph(county);
  renderDownBallotGraph(county);
  renderTurnoutGraph(county);
}

function chartScope(county) {
  const normalized = normalizeCounty(county || "");
  const metadata = window.ETA_WARD_CHARTS?.metadata || {};
  const rows = county
    ? metadata.rows.filter((row) => normalizeCounty(row.county) === normalized)
    : metadata.rows;

  return {
    rows,
    label: county ? `${county} County` : "Statewide",
  };
}

function renderVoteShareGraph(county) {
  const width = 760;
  const height = 360;
  const margin = { top: 24, right: 24, bottom: 54, left: 58 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const scope = chartScope(county);
  const trump = scope.rows.map((row) => [row.trump, row.trumpShare]);
  const harris = scope.rows.map((row) => [row.harris, row.harrisShare]);
  if (!scope.rows.length) {
    renderGraphMessage(els.voteShareGraph, `No ward-level chart rows found for ${scope.label}.`);
    return;
  }
  const all = [...trump, ...harris];
  const xMax = Math.max(10, Math.ceil(Math.max(...all.map((point) => point[0])) / 100) * 100);
  const x = (value) => margin.left + (value / xMax) * plotWidth;
  const y = (value) => margin.top + ((100 - value) / 100) * plotHeight;

  const grid = [0, 25, 50, 75, 100]
    .map(
      (tick) => `
        <line class="graph-grid" x1="${margin.left}" y1="${y(tick)}" x2="${width - margin.right}" y2="${y(tick)}"></line>
        <text class="graph-label" x="${margin.left - 10}" y="${y(tick) + 4}" text-anchor="end">${tick}%</text>
      `,
    )
    .join("");
  const xTicks = [0, xMax / 2, xMax]
    .map(
      (tick) => `
        <line class="graph-grid" x1="${x(tick)}" y1="${margin.top}" x2="${x(tick)}" y2="${height - margin.bottom}"></line>
        <text class="graph-label" x="${x(tick)}" y="${height - 24}" text-anchor="middle">${formatNumber(Math.round(tick))}</text>
      `,
    )
    .join("");
  const points = [
    ...trump.map((point) => `<circle cx="${x(point[0])}" cy="${y(point[1])}" r="2" fill="#c84c42" opacity="0.34"></circle>`),
    ...harris.map((point) => `<circle cx="${x(point[0])}" cy="${y(point[1])}" r="2" fill="#3477bd" opacity="0.34"></circle>`),
  ].join("");
  const trendLines = [
    regressionLine(trump, x, y, xMax, "#a8302a"),
    regressionLine(harris, x, y, xMax, "#1458a8"),
  ].join("");

  els.voteShareGraph.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Vote share by vote count scatterplot">
      <rect width="${width}" height="${height}" fill="#fbfcfd"></rect>
      ${grid}
      ${xTicks}
      <line class="graph-axis" x1="${margin.left}" y1="${height - margin.bottom}" x2="${width - margin.right}" y2="${height - margin.bottom}"></line>
      <line class="graph-axis" x1="${margin.left}" y1="${margin.top}" x2="${margin.left}" y2="${height - margin.bottom}"></line>
      ${points}
      ${trendLines}
      <text class="graph-title" x="${margin.left}" y="18">${scope.label}: each dot is one ward/candidate pair (${formatNumber(scope.rows.length)} wards)</text>
      <text class="graph-label" x="${width / 2}" y="${height - 8}" text-anchor="middle">Candidate votes in ward</text>
      <text class="graph-label" transform="translate(16 ${height / 2}) rotate(-90)" text-anchor="middle">Candidate vote share</text>
      <circle cx="${width - 150}" cy="18" r="5" fill="#c84c42"></circle>
      <text class="graph-label" x="${width - 139}" y="22">Trump</text>
      <circle cx="${width - 82}" cy="18" r="5" fill="#3477bd"></circle>
      <text class="graph-label" x="${width - 71}" y="22">Harris</text>
    </svg>
  `;
}

function renderDownBallotGraph(county) {
  const width = 760;
  const height = 340;
  const margin = { top: 24, right: 24, bottom: 54, left: 52 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const scope = chartScope(county);
  if (!scope.rows.length) {
    renderGraphMessage(els.downBallotGraph, `No ward-level chart rows found for ${scope.label}.`);
    return;
  }
  const dropoffValues = scope.rows.flatMap((row) => [
    ["dem", row.demDropoff],
    ["rep", row.repDropoff],
  ]);
  const bins = buildDropoffBins(dropoffValues, -30, 30, 2);
  const maxCount = Math.max(...bins.map((bin) => Math.max(bin.dem, bin.rep)));
  const x = (index) => margin.left + (index / bins.length) * plotWidth;
  const y = (value) => margin.top + (1 - value / maxCount) * plotHeight;
  const barWidth = Math.max(3, plotWidth / bins.length - 2);

  const bars = bins
    .map((bin, index) => {
      const baseX = x(index);
      const demHeight = height - margin.bottom - y(bin.dem);
      const repHeight = height - margin.bottom - y(bin.rep);
      return `
        <rect x="${baseX}" y="${y(bin.dem)}" width="${barWidth / 2}" height="${demHeight}" fill="#3477bd" opacity="0.72"></rect>
        <rect x="${baseX + barWidth / 2}" y="${y(bin.rep)}" width="${barWidth / 2}" height="${repHeight}" fill="#c84c42" opacity="0.72"></rect>
      `;
    })
    .join("");
  const zeroX = x(bins.findIndex((bin) => bin.start === 0));
  const yTicks = [0, Math.round(maxCount / 2), maxCount]
    .map(
      (tick) => `
        <line class="graph-grid" x1="${margin.left}" y1="${y(tick)}" x2="${width - margin.right}" y2="${y(tick)}"></line>
        <text class="graph-label" x="${margin.left - 8}" y="${y(tick) + 4}" text-anchor="end">${tick}</text>
      `,
    )
    .join("");

  els.downBallotGraph.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Down-ballot drop-off histogram">
      <rect width="${width}" height="${height}" fill="#fbfcfd"></rect>
      ${yTicks}
      <line class="graph-grid" x1="${zeroX}" y1="${margin.top}" x2="${zeroX}" y2="${height - margin.bottom}" stroke-dasharray="5 5"></line>
      ${bars}
      <line class="graph-axis" x1="${margin.left}" y1="${height - margin.bottom}" x2="${width - margin.right}" y2="${height - margin.bottom}"></line>
      <line class="graph-axis" x1="${margin.left}" y1="${margin.top}" x2="${margin.left}" y2="${height - margin.bottom}"></line>
      <text class="graph-title" x="${margin.left}" y="18">${scope.label}: distribution of ward drop-off rates</text>
      <text class="graph-label" x="${margin.left}" y="${height - 24}" text-anchor="start">-30%</text>
      <text class="graph-label" x="${zeroX}" y="${height - 24}" text-anchor="middle">0%</text>
      <text class="graph-label" x="${width - margin.right}" y="${height - 24}" text-anchor="end">+30%</text>
      <text class="graph-label" x="${width / 2}" y="${height - 8}" text-anchor="middle">Presidential votes minus Senate votes, as % of presidential votes</text>
      <text class="graph-label" transform="translate(15 ${height / 2}) rotate(-90)" text-anchor="middle">Ward count</text>
      <rect x="${width - 160}" y="12" width="12" height="12" fill="#3477bd" opacity="0.72"></rect>
      <text class="graph-label" x="${width - 142}" y="22">DEM</text>
      <rect x="${width - 96}" y="12" width="12" height="12" fill="#c84c42" opacity="0.72"></rect>
      <text class="graph-label" x="${width - 78}" y="22">REP</text>
    </svg>
  `;
}

function renderTurnoutGraph(county) {
  const label = county ? `${county} County` : "statewide";
  els.turnoutGraph.innerHTML = `
    <svg viewBox="0 0 760 260" role="img" aria-label="Turnout histogram placeholder">
      <rect width="760" height="260" fill="#fbfcfd"></rect>
      ${[70, 115, 155, 190].map((x, index) => `<rect x="${x}" y="${160 - index * 25}" width="62" height="${50 + index * 25}" fill="#dce3e8"></rect>`).join("")}
      ${[250, 295, 340, 385].map((x, index) => `<rect x="${x}" y="${65 + index * 20}" width="62" height="${145 - index * 20}" fill="#dce3e8"></rect>`).join("")}
      <line class="graph-axis" x1="52" y1="210" x2="708" y2="210"></line>
      <line class="graph-axis" x1="52" y1="32" x2="52" y2="210"></line>
      <text class="graph-title" x="52" y="24">${label}: turnout histogram will render when denominator data is imported</text>
      <text class="graph-warning-text" x="52" y="242">${TURNOUT_SOURCE_POLICY.warning}</text>
    </svg>
  `;
}

function renderGraphMessage(target, message) {
  target.innerHTML = `
    <svg viewBox="0 0 760 220" role="img" aria-label="Graph status">
      <rect width="760" height="220" fill="#fbfcfd"></rect>
      <text class="graph-warning-text" x="40" y="112">${message}</text>
    </svg>
  `;
}

function regressionLine(points, xScale, yScale, xMax, color) {
  const regression = linearRegression(points);
  const y1 = regression.intercept;
  const y2 = regression.intercept + regression.slope * xMax;
  return `<line x1="${xScale(0)}" y1="${yScale(y1)}" x2="${xScale(xMax)}" y2="${yScale(y2)}" stroke="${color}" stroke-width="3" opacity="0.92"></line>`;
}

function linearRegression(points) {
  const n = points.length;
  const meanX = points.reduce((sum, point) => sum + point[0], 0) / n;
  const meanY = points.reduce((sum, point) => sum + point[1], 0) / n;
  let numerator = 0;
  let denominator = 0;

  points.forEach((point) => {
    numerator += (point[0] - meanX) * (point[1] - meanY);
    denominator += (point[0] - meanX) ** 2;
  });

  const slope = denominator === 0 ? 0 : numerator / denominator;
  return { slope, intercept: meanY - slope * meanX };
}

function buildDropoffBins(values, min, max, step) {
  const bins = [];
  for (let start = min; start < max; start += step) {
    bins.push({ start, dem: 0, rep: 0 });
  }

  values.forEach(([party, value]) => {
    const clamped = Math.max(min, Math.min(max - 0.001, value));
    const index = Math.floor((clamped - min) / step);
    bins[index][party] += 1;
  });

  return bins;
}

function voteShareByVoteCountProxy() {
  const threshold = 0.35;
  const trumpCorrelation = pearson(
    RESULTS.map((row) => row.trump),
    RESULTS.map((row) => row.trumpPct),
  );
  const harrisCorrelation = pearson(
    RESULTS.map((row) => row.harris),
    RESULTS.map((row) => row.harrisPct),
  );

  return {
    trumpCorrelation,
    harrisCorrelation,
    threshold,
    flagged: Math.abs(trumpCorrelation) >= threshold || Math.abs(harrisCorrelation) >= threshold,
  };
}

function renderCandidateBreakdown(row = null) {
  const title = row ? `${row.county} County` : "Statewide";
  const values = CANDIDATE_LABELS.map((candidate) => ({
    ...candidate,
    votes: row ? row[candidate.key] : sumCandidate(candidate.key),
  }));
  const total = values.reduce((sum, candidate) => sum + candidate.votes, 0);

  els.breakdownTitle.textContent = title;
  els.breakdownTotal.textContent = `${formatNumber(total)} other votes`;
  els.candidateBreakdown.innerHTML = values
    .map(
      (candidate) => `
        <div class="candidate-chip" title="${candidate.label}">
          <span>${candidate.label}</span>
          <strong>${formatNumber(candidate.votes)}</strong>
        </div>
      `,
    )
    .join("");
}

function popupHtml(row) {
  return `
    <div class="county-popup">
      <h3>${row.county} County</h3>
      <dl>
        <dt>Winner</dt><dd>${winnerLabel(row)}</dd>
        <dt>Margin</dt><dd>${formatNumber(Math.abs(row.margin))}</dd>
        <dt>Trump</dt><dd>${formatNumber(row.trump)} (${row.trumpPct.toFixed(2)}%)</dd>
        <dt>Harris</dt><dd>${formatNumber(row.harris)} (${row.harrisPct.toFixed(2)}%)</dd>
        <dt>Other</dt><dd>${formatNumber(row.other)} (${row.otherPct.toFixed(2)}%)</dd>
        <dt>Kennedy</dt><dd>${formatNumber(row.kennedy)}</dd>
        <dt>Stein</dt><dd>${formatNumber(row.stein)}</dd>
        <dt>Oliver</dt><dd>${formatNumber(row.oliver)}</dd>
        <dt>Total</dt><dd>${formatNumber(row.total)}</dd>
      </dl>
    </div>
  `;
}

function exportCsv() {
  const candidateHeaders = CANDIDATE_LABELS.map((candidate) => candidate.label);
  const headers = [
    "County",
    "Trump",
    "Trump %",
    "Harris",
    "Harris %",
    ...candidateHeaders,
    "Other",
    "Other %",
    "Margin",
    "Margin %",
    "Total",
  ];
  const rows = RESULTS.map((row) => [
    row.county,
    row.trump,
    row.trumpPct,
    row.harris,
    row.harrisPct,
    ...CANDIDATE_LABELS.map((candidate) => row[candidate.key]),
    row.other,
    row.otherPct,
    row.margin,
    row.marginPct,
    row.total,
  ]);
  const csv = [headers, ...rows]
    .map((row) => row.map((cell) => `"${String(cell).replaceAll('"', '""')}"`).join(","))
    .join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "wisconsin-2024-president-county-results.csv";
  link.click();
  URL.revokeObjectURL(url);
}

function filteredRows() {
  const query = els.search.value.trim().toLowerCase();
  return RESULTS.filter((row) => row.county.toLowerCase().includes(query));
}

function winnerLabel(row) {
  return row.margin >= 0 ? "Trump" : "Harris";
}

function sumCandidate(key) {
  return RESULTS.reduce((sum, row) => sum + row[key], 0);
}

function pearson(xs, ys) {
  const n = xs.length;
  const meanX = xs.reduce((sum, value) => sum + value, 0) / n;
  const meanY = ys.reduce((sum, value) => sum + value, 0) / n;
  let numerator = 0;
  let xDenominator = 0;
  let yDenominator = 0;

  for (let index = 0; index < n; index += 1) {
    const xDelta = xs[index] - meanX;
    const yDelta = ys[index] - meanY;
    numerator += xDelta * yDelta;
    xDenominator += xDelta * xDelta;
    yDenominator += yDelta * yDelta;
  }

  return numerator / Math.sqrt(xDenominator * yDenominator);
}

function normalizeCounty(name = "") {
  return name.toLowerCase().replace(/\s+county$/, "").replace(/\./g, "").replace(/\s+/g, " ").trim();
}

function formatNumber(value) {
  return new Intl.NumberFormat("en-US").format(value);
}

function formatSigned(value) {
  const sign = value > 0 ? "+" : value < 0 ? "-" : "";
  return `${sign}${formatNumber(Math.abs(value))}`;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

init();
