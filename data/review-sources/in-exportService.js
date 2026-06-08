(function () {
    'use strict';

    angular
        .module('enrServicesModule')
        .factory('exportService', ['$filter', exportService]);

    function exportService($filter) {
        // #region PRIVARTE MEMBERS
        var CSV = '';
        var row = '';
        var rowData = '';

        // #endregion

        // #region SERVICE INTERFACE
        var service = {
            toCsv: exportToCSV,
            toJSON: exportToJSON,
            toXML: exportToXML
        };

        return service;
        // #endregion

        // #region PRIVATE

        function exportToCSV(exportData, pageName) {
            var arrData = typeof exportData != 'object' ? JSON.parse(exportData) : exportData;
            var formatter = new Intl.NumberFormat('en-US', {
                style: 'currency',
                currency: 'USD',
                minimumFractionDigits: 2,
            });

            CSV = '';
            row = '';
            rowData = '';
            if (arrData != undefined || pageName == 'VoterStatistics') {
                VoterStatisticsCsv(arrData);
            }


            if (CSV != '') {
                generateCsv();
            }
        }

        // Preapring Voter Statistics Data
        function VoterStatisticsCsv(arrObj) {
            var arrData1 = [];
            var Columns = ['County', 'RegisteredVoters', 'VotersVoting', 'TurnOut', 'Electionday', 'Absentee', 'AbsenteePercentage'];
            angular.forEach(arrObj, function (element, index) {
                var voterVotingRigisterVoters = element.VotersVoting / element.REGISTERED_VOTERS;
                var AbsenteeVotingRigisterVoters = element.Absentee / element.VotersVoting;

                arrData1.push({
                    'County': element.County,
                    'RegisteredVoters': element.REGISTERED_VOTERS,
                    'VotersVoting': element.VotersVoting,
                    'TurnOut': isNaN(voterVotingRigisterVoters) || voterVotingRigisterVoters == Infinity ? '' : voterVotingRigisterVoters,
                    'Electionday': element.InPerson,
                    'Absentee': element.Absentee,
                    'AbsenteePercentage': isNaN(AbsenteeVotingRigisterVoters) || AbsenteeVotingRigisterVoters == Infinity ? '' : AbsenteeVotingRigisterVoters,

                });
            });

            //$filter('percentage')(arrData1, 0);

            angular.forEach(arrData1, function (Data, index) {
                rowData = '';
                angular.forEach(Data, function (Data, headerName) {
                    if (Columns.indexOf(headerName) != -1) {
                        if (index == 0) {
                            if (headerName == 'County') {
                                headerName = 'County';
                            }
                            else if (headerName == 'RegisteredVoters') {
                                headerName = 'Registered Voters';
                            }
                            else if (headerName == 'VotersVoting') {
                                headerName = 'Voters Voting';
                            }
                            else if (headerName == 'TurnOut') {
                                headerName = 'TurnOut %';
                            }
                            else if (headerName == 'Electionday') {
                                headerName = 'Election Day';
                            }
                            else if (headerName == 'Absentee') {
                                headerName = 'Absentee';
                            }
                            else if (headerName == 'AbsenteePercentage') {
                                headerName = 'Absentee %';
                            }

                            row += headerName + ',';
                        }
                        if (typeof Data === 'string') {
                            if (Data) {
                                if (Data.indexOf(',') != -1) {
                                    Data = '"' + Data + '"';
                                }
                            }
                        }
                        else {
                            if (!Data) {
                                Data = '';
                            }
                            else {
                                Data = Data;
                            }
                        }
                        if (headerName == 'TurnOut' || headerName == 'AbsenteePercentage' || headerName == 'TurnOut %' || headerName == 'Absentee %') {
                            rowData += (Data * 100).toFixed(0) + '%' + ',';
                        }
                        else {
                            rowData += Data + ',';
                        }

                    }
                });
                if (index == 0) {
                    row = row.slice(0, -1);
                    //append Label row with line break
                    CSV += row + '\r\n';
                }
                rowData.slice(0, rowData.length - 1);
                //add a line break after each row
                CSV += rowData + '\r\n';
            });
        }



        function formatter() {
            return new Intl.NumberFormat('en-US', {
                style: 'currency',
                currency: 'USD',
                minimumFractionDigits: 2,
            });
        }



        // Generates CSV file
        function generateCsv() {
            // Generate a file name
            var fileName = 'VoterStatistics';
            // this will remove the blank-spaces from the title and replace it with an underscore
            // fileName += ReportTitle.replace(/ /g, '_');

            //Initialize file format you want csv or xls
            var uri = 'data:text/csv;charset=utf-8,' + escape(CSV);

            // Now the little tricky part.
            // you can use either>> window.open(uri);
            // but this will not work in some browsers
            // or you will not get the correct file extension    

            //this trick will generate a temp <a /> tag
            if (navigator.msSaveBlob) {
                // var blob = new Blob([CSV], { type: 'text/csv;charset=utf-8;' });
                //  navigator.msSaveBlob(blob, 'fileName.csv')

                var textEncoder = new CustomTextEncoder('windows-1252', { NONSTANDARD_allowLegacyEncoding: true });
                var csvContentEncoded = textEncoder.encode([CSV]); // Encodes CSV into windows 1252 format
                var blob = new Blob([csvContentEncoded], { type: 'text/csv;charset=windows-1252;' });
                saveAs(blob, fileName + '.csv');
            }
            else {
                var link = document.createElement('a');
                link.href = uri;

                //set the visibility hidden so it will not effect on your web-layout
                link.style = 'visibility:hidden';
                link.download = fileName + '.csv';

                //this part will append the anchor tag and remove it after automatic click
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
            }
            CSV = '';
            row = '';
            rowData = '';
        }

        function setDateZero(date) {
            return date < 10 ? '0' + date : date;
        }


        function exportToJSON(exportData, pageName) {
            //check response is undefined, null or empty
            if (typeof exportData == 'undefined' || exportData == null || exportData == "")
                return;

            var myJsonString = JSON.stringify(exportData);
            var blob = new Blob([myJsonString], { type: 'application/json' });
            saveAs(blob, pageName + '.json');

        }

        function exportToXML(exportData, pageName) {

            //check response is undefined, null or empty
            if (typeof exportData == 'undefined' || exportData == null || exportData == "")
                return;
            var doc = $.parseXML("<" + pageName + "/>");
            var xml = doc.getElementsByTagName(pageName)[0];
            var key, elem, percent;

            angular.forEach(exportData, function (element, index) {
                var elemData = doc.createElement("Data");
                for (var key in element) {
                    elem = doc.createElement(key);
                    $(elem).text(element[key]);
                    elemData.appendChild(elem);
                };
                xml.appendChild(elemData);
            });
            if (navigator.msSaveBlob) {
                var oSerializer = new XMLSerializer();
                var sXML = oSerializer.serializeToString(xml);
                var blob = new Blob([sXML], { type: 'text/xml' });
                saveAs(blob, pageName + '.xml');
            }
            else {
                var element = document.createElement('a');
                element.setAttribute('href', 'data:text/plain;charset=utf-8,' + escape(xml.outerHTML));
                element.setAttribute('download', pageName + ".xml");
                element.style.display = 'none';
                document.body.appendChild(element);
                element.click();
                document.body.removeChild(element);

            }
        }
        // #endregion
    }
})();
