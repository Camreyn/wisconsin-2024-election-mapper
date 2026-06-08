(function () {

    "use strict";

    // "Private" members
    var dataPath = "data/";
    var clientDataPath = "clientData/";
    var version = "";
    var trimJsonRoot = function (json) { return json.Root === undefined ? json : json.Root; }
    var buildFullFilePath = function (fileName, isVersioned, isClientData) {
        var dataPathToUse = isClientData ? clientDataPath : dataPath;
        return dataPathToUse + fileName + (isVersioned ? ("_" + version) : "") + ".json";
    }

    angular.module("jsonDataFetcherModule", [])
        .factory("jsonDataFetcher", ["$http", "$q", "errorHandler", function ($http, $q, errorHandler) {
            var onFetchError = function(response, fileName) {
                var msgString;
                var isCorruptJson = response.data === undefined &&
                    response.config === undefined &&
                    response.status === undefined;
                if (isCorruptJson) {
                    msgString = "\"" + fileName + "\" data is corrupt.";
                } else {
                    msgString = "Failed to retrieve \"" + fileName + "\" data due to " + response.status + " error.";
                }
                errorHandler.handleError(msgString);
            }

            return {
                // Fetch a single json file.
                fetchSingleJson: function (fileName, isVersioned, isClientData, fetchSuccessfulCallback) {
                    var fullFilePath = buildFullFilePath(fileName, isVersioned, isClientData);

                    $http.get(fullFilePath)
                        .then(function (response) {
                            var returnJson = trimJsonRoot(response.data);
                            fetchSuccessfulCallback(returnJson);
                        })
                        .catch(function(response) {
                            onFetchError(response, fileName);
                        });
                },

                // Fetch multiple json files simultaneously. Will only execute provided callback once all files are retrieved. 
                fetchMultipleJson: function (fileNames, areVersioned, areClientData, fetchSuccessfulCallback) {

                    // Begin simultaneous retrieval
                    var promiseArray = [];
                    for (var i = 0; i < fileNames.length; i++) {
                        var fullFilePath = buildFullFilePath(fileNames[i], areVersioned[i], areClientData[i]);
                        promiseArray.push($http.get(fullFilePath));
                    }

                    // Process all fetches as a single promise.
                    $q.all(promiseArray)
                        .then(function (jsonArray) {
                            for (var j = 0; j < fileNames.length; j++) {
                                jsonArray[j] = (trimJsonRoot(jsonArray[j].data));
                            }
                            fetchSuccessfulCallback(jsonArray);
                        })
                        .catch(function (response) {
                            onFetchError(response, fileNames);
                        });
                },

                // Tell jsonDataFetcher what version to use so it can automatically include it in JSON requests.
                registerVersion: function (curVersion) {
                    version = curVersion;
                },

                // Tell jsonDataFetcher what version to use so it can automatically include it in JSON requests.
                registerElectionType: function (_electionType) {
                    electionType = _electionType;
                }
            };
        }]);
}());