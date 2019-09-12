import copy
import json
import os
from os import path
import fcntl


class BenchmarkResult:
    """
    The result of a benchmark run for a particular benchmark function, given
    specific args.
    """
    def __init__(self, funcName, argNameValuePairs, result):
        self.name = funcName
        self.argNameValuePairs = copy.deepcopy(argNameValuePairs)
        self.result = result


class BenchmarkInfo:
    """
    Meta-data describing the environment for a benchmark or set of benchmarks.
    """
    def __init__(self, machineName, cudaVer, osType, pythonVer, commitHash, commitTime,
                 gpuType="", cpuType="", arch="", ram=""):
        self.machineName = machineName
        self.cudaVer = cudaVer
        self.osType = osType
        self.pythonVer = pythonVer
        self.commitHash = commitHash
        self.commitTime = commitTime

        self.gpuType = gpuType
        self.cpuType = cpuType
        self.arch = arch
        self.ram = ram


class ASVDb:
    """
    A "database" of benchmark results consumable by ASV.
    https://asv.readthedocs.io/en/stable/dev.html?highlight=%24results_dir#benchmark-suite-layout-and-file-formats
    """
    confFileName = "asv.conf.json"
    defaultResultsDirName = "results"
    defaultHtmlDirName = "html"
    defaultConfVersion = 1.0
    benchmarksFileName = "benchmarks.json"
    machineFileName = "machine.json"

    def __init__(self, dbDir, repo, branches=None):
        """
        dbDir -
        repo -
        branches - https://asv.readthedocs.io/en/stable/asv.conf.json.html#branches
        """
        self.dbDir = dbDir
        self.confFilePath = path.join(self.dbDir, self.confFileName)
        d = self.__getJsonDictFromFile(self.confFilePath)

        self.confVersion = self.defaultConfVersion
        self.resultsDirName = d.setdefault("results_dir", self.defaultResultsDirName)
        self.resultsDirPath = path.join(dbDir, self.resultsDirName)
        self.htmlDirName = d.setdefault("html_dir", self.defaultHtmlDirName)
        self.benchmarksFilePath = path.join(self.resultsDirPath, self.benchmarksFileName)

        d["repo"] = repo
        d["branches"] = branches or []
        d["version"] = 1.0

        # FIXME: consider a separate method for writing this file, ctor may not
        # be appropriate
        self.__writeJsonDictToFile(d, self.confFilePath)


    def addResult(self, benchmarkInfo, benchmarkResult):
        self.__updateBenchmarkJson(benchmarkResult)
        self.__updateMachineJson(benchmarkInfo)
        self.__updateResultJson(benchmarkResult, benchmarkInfo)


    def __updateBenchmarkJson(self, benchmarkResult):
        # The following is an example of the schema ASV expects for
        # `benchmarks.json`.  If param names are A, B, and C
        #
        # {
        #     "<algo name>": {
        #         "code": "",
        #         "name": "<algo name>",
        #         "param_names": [
        #             "A", "B", "C"
        #         ],
        #     "params": [
        #                [<value1 for A>,
        #                 <value2 for A>,
        #                ],
        #                [<value1 for B>,
        #                 <value2 for B>,
        #                ],
        #                [<value1 for C>,
        #                 <value2 for C>,
        #                ],
        #               ],
        #         "timeout": 60,
        #         "type": "time",
        #         "unit": "seconds",
        #         "version": 1,
        #     }
        # }

        newParamNames = []
        newParamValues = []
        for (n, v) in benchmarkResult.argNameValuePairs:
            newParamNames.append(n)
            newParamValues.append(v)

        d = self.__getJsonDictFromFile(self.benchmarksFilePath)

        benchDict = d.setdefault(benchmarkResult.name,
                                 self.__getDefaultBenchmarkDescrDict(
                                     benchmarkResult.name, newParamNames))

        existingParamNames = benchDict["param_names"]
        existingParamValues = benchDict["params"]

        # Check for the case where a result came in for the function, but it has
        # a different number of args vs. what was saved previously
        numExistingParams = len(existingParamNames)
        numNewParams = len(newParamNames)
        if numExistingParams != numNewParams:
            raise ValueError("result for %s had %d args in benchmarks.json, "
                             "but new result has %d args" \
                             % (benchmarkResult.name, numExistingParams,
                                numNewParams))
        numParams = numNewParams

        # assume the number of param values for each param is the same
        if existingParamValues:
            numExistingParamValues = len(existingParamValues[0])
        else:
            numExistingParamValues = 0

        # check if the set of args is aleady present (eg. just a re-run of the
        # same benchmark) and if so do not add the param values again.
        skip = False
        for i in range(numExistingParamValues):
            evals = []
            for vals in existingParamValues:
                evals.append(vals[i])
            if newParamValues == evals:
                print("Benchmark with param values already exist, not adding to benchmarks.json")
                skip = True
                break

        if not skip:
            if numExistingParamValues == 0:
                for newVal in newParamValues:
                    existingParamValues.append([newVal])
            else:
                for i in range(numParams):
                    existingParamValues[i].append(newParamValues[i])

        d[benchmarkResult.name] = benchDict

        # a version key must always be present in self.benchmarksFilePath,
        # "current" ASV version requires this to be 2 (or higher?)
        d["version"] = 2
        self.__writeJsonDictToFile(d, self.benchmarksFilePath)


    def __updateMachineJson(self, benchmarkInfo):
        # The following is an example of the schema ASV expects for
        # `machine.json`.
        # {
        #     "arch": "x86_64",
        #     "cpu": "Intel, ...",
        #     "machine": "sm01",
        #     "os": "Linux ...",
        #     "ram": "123456",
        #     "version": 1,
        # }

        resultsFilePath = path.join(self.resultsDirPath,
                                    benchmarkInfo.machineName,
                                    self.machineFileName)
        d = self.__getJsonDictFromFile(resultsFilePath)
        d["arch"] = benchmarkInfo.arch
        d["cpu"] = benchmarkInfo.cpuType
        d["gpu"] = benchmarkInfo.gpuType
        d["cuda"] = benchmarkInfo.cudaVer
        d["machine"] = benchmarkInfo.machineName
        d["os"] = benchmarkInfo.osType
        d["ram"] = benchmarkInfo.ram
        d["version"] = 1
        self.__writeJsonDictToFile(d, resultsFilePath)


    def __updateResultJson(self, benchmarkResult, benchmarkInfo):
        # The following is an example of the schema ASV expects for
        # '<machine>-<commit_hash>.json'. If param names are A, B, and C
        #
        # {
        #     "params": {
        #         "cuda": "9.2",
        #         "gpu": "Tesla ...",
        #         "machine": "sm01",
        #         "os": "Linux ...",
        #         "python": "3.7",
        #     },
        #     "requirements": {},
        #     "results": {
        #         "<algo name>": {
        #             "params": [
        #                        [<value1 for A>,
        #                         <value2 for A>,
        #                        ],
        #                        [<value1 for B>,
        #                         <value2 for B>,
        #                        ],
        #                        [<value1 for C>,
        #                         <value2 for C>,
        #                        ],
        #                       ]
        #             "result": [
        #                        <result1>,
        #                        <result2>,
        #                       ]
        #         },
        #     },
        #     "commit_hash": "321e321321eaf",
        #     "date": 12345678,
        #     "python": "3.7",
        #     "version": 1,
        # }

        resultsFilePath = path.join(self.resultsDirPath,
                                    benchmarkInfo.machineName,
                                    "%s.json" % (benchmarkInfo.commitHash))
        d = self.__getJsonDictFromFile(resultsFilePath)
        d["params"] = {"gpu": benchmarkInfo.gpuType,
                       "cuda": benchmarkInfo.cudaVer,
                       "machine": benchmarkInfo.machineName,
                       "os": benchmarkInfo.osType,
                       "python": benchmarkInfo.pythonVer,
                       }
        d["requirements"] = {}
        resultsDict = d.setdefault("results", {})
        resultDict = resultsDict.setdefault(benchmarkResult.name, {})

        resultParamValues = [v for (_, v) in benchmarkResult.argNameValuePairs]

        # Transform the params list to: [[v1A, v1B, v1C], [v2A, v2B, v2C]]
        # for easy searching.
        existingParamValuesList = [list(l) for l in zip(*resultDict.setdefault("params", []))]

        existingResultValueList = resultDict.setdefault("result", [])

        # check if the set of param values are already in the 'params' list, and
        # if so, just update the corresponding result
        if resultParamValues in existingParamValuesList:
            i = existingParamValuesList.index(resultParamValues)
            existingResultValueList[i] = benchmarkResult.result

        # if these are new param values, then append to the existing set of
        # param values and append another result
        else:
            existingParamValuesList.append(resultParamValues)
            existingResultValueList.append(benchmarkResult.result)
            # transform the params list back to:
            # [[v1A, v2A], [v1B, v2B], [v1C, v2C]]
            # and store it now that it has new params
            resultDict["params"] = [list(l) for l in zip(*existingParamValuesList)]

        d["commit_hash"] = benchmarkInfo.commitHash
        d["date"] = benchmarkInfo.commitTime
        d["python"] = benchmarkInfo.pythonVer
        d["version"] = 1

        self.__writeJsonDictToFile(d, resultsFilePath)


    def __getDefaultBenchmarkDescrDict(self, funcName, paramNames):
        return {"code": funcName,
                "name": funcName,
                "param_names": paramNames,
                "params": [],
                "timeout": 60,
                "type": "time",
                "unit": "seconds",
                "version": 2,
                }


    def __getJsonDictFromFile(self, jsonFile):
        """
        Return a dictionary representing the contents of jsonFile by
        either reading in the existing file or returning {}
        """
        if path.exists(jsonFile):
            with open(jsonFile) as fobj:
                # some situations do not allow grabbing a file lock (NFS?) so
                # just ignore for now (TODO: use a different locking mechanism)
                try:
                    fcntl.flock(fobj, fcntl.LOCK_EX)
                except OSError:
                    pass
                # FIXME: error checking
                return json.load(fobj)

        return {}


    def __writeJsonDictToFile(self, jsonDict, filePath):
        # FIXME: error checking
        dirPath = path.dirname(filePath)
        if not path.isdir(dirPath):
            os.makedirs(dirPath)
        with open(filePath, "w") as fobj:
            # some situations do not allow grabbing a file lock (NFS?) so just
            # ignore for now (TODO: use a different locking mechanism)
            try:
                fcntl.flock(fobj, fcntl.LOCK_EX)
            except OSError:
                pass
            json.dump(jsonDict, fobj, indent=2)
