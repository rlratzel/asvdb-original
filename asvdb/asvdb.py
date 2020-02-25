import json
import os
from os import path
import fcntl
import itertools


class BenchmarkResult:
    """
    The result of a benchmark run for a particular benchmark function, given
    specific args.
    """
    def __init__(self, funcName, argNameValuePairs, result):
        self.name = funcName
        self.argNameValuePairs = self.__sanitizeArgNameValues(argNameValuePairs)
        self.result = result
        self.unit = "seconds"

    def __sanitizeArgNameValues(self, argNameValuePairs):
        return [(n, str(v if v is not None else "NaN")) for (n, v) in argNameValuePairs]


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
        self.commitTime = int(commitTime)

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
    defaultConfVersion = 1
    benchmarksFileName = "benchmarks.json"
    machineFileName = "machine.json"

    def __init__(self, dbDir, repo, branches=None, projectName=None, commitUrl=None):
        """
        dbDir -
        repo -
        branches - https://asv.readthedocs.io/en/stable/asv.conf.json.html#branches
        """
        self.dbDir = dbDir
        self.confFilePath = path.join(self.dbDir, self.confFileName)
        d = self.__loadJsonDictFromFile(self.confFilePath)

        self.confVersion = self.defaultConfVersion
        self.resultsDirName = d.setdefault("results_dir", self.defaultResultsDirName)
        self.resultsDirPath = path.join(dbDir, self.resultsDirName)
        self.htmlDirName = d.setdefault("html_dir", self.defaultHtmlDirName)
        self.benchmarksFilePath = path.join(self.resultsDirPath, self.benchmarksFileName)

        # ASVDb is git-only for now, so ensure .git extension
        d["repo"] = repo + (".git" if not repo.endswith(".git") else "")
        currentBranches = d.get("branches", [])
        d["branches"] = currentBranches + [b for b in (branches or []) if b not in currentBranches]
        d["version"] = 1
        d["project"] = projectName or repo.replace(".git", "").split("/")[-1]
        d["show_commit_url"] = commitUrl or \
                               (repo.replace(".git", "") \
                                + ("/" if not repo.endswith("/") else "") \
                                + "commit/")

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

        d = self.__loadJsonDictFromFile(self.benchmarksFilePath)

        benchDict = d.setdefault(benchmarkResult.name,
                                 self.__getDefaultBenchmarkDescrDict(
                                     benchmarkResult.name, newParamNames))
        benchDict["unit"] = benchmarkResult.unit

        existingParamNames = benchDict["param_names"]
        existingParamValues = benchDict["params"]

        numExistingParams = len(existingParamNames)
        numExistingParamValues = len(existingParamValues)
        numNewParams = len(newParamNames)

        # Check for the case where a result came in for the function, but it has
        # a different number of args vs. what was saved previously
        if numExistingParams != numNewParams:
            raise ValueError("result for %s had %d params in benchmarks.json, "
                             "but new result has %d params" \
                             % (benchmarkResult.name, numExistingParams,
                                numNewParams))
        numParams = numNewParams

        cartProd = list(itertools.product(*existingParamValues))
        if tuple(newParamValues) not in cartProd:
            if numExistingParamValues == 0:
                for newVal in newParamValues:
                    existingParamValues.append([newVal])
            else:
                for i in range(numParams):
                    if newParamValues[i] not in existingParamValues[i]:
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

        machineFilePath = path.join(self.resultsDirPath,
                                    benchmarkInfo.machineName,
                                    self.machineFileName)
        d = self.__loadJsonDictFromFile(machineFilePath)
        d["arch"] = benchmarkInfo.arch
        d["cpu"] = benchmarkInfo.cpuType
        d["gpu"] = benchmarkInfo.gpuType
        #d["cuda"] = benchmarkInfo.cudaVer
        d["machine"] = benchmarkInfo.machineName
        #d["os"] = benchmarkInfo.osType
        d["ram"] = benchmarkInfo.ram
        d["version"] = 1
        self.__writeJsonDictToFile(d, machineFilePath)


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

        resultsFilePath = self.__getResultsFilePath(benchmarkInfo)
        d = self.__loadJsonDictFromFile(resultsFilePath)
        d["params"] = {"gpu": benchmarkInfo.gpuType,
                       "cuda": benchmarkInfo.cudaVer,
                       "machine": benchmarkInfo.machineName,
                       "os": benchmarkInfo.osType,
                       "python": benchmarkInfo.pythonVer,
                       }
        d["requirements"] = {}
        allResultsDict = d.setdefault("results", {})
        resultDict = allResultsDict.setdefault(benchmarkResult.name, {})

        existingParamValuesList = resultDict.setdefault("params", [])
        existingResultValueList = resultDict.setdefault("result", [])

        # FIXME: dont assume these are ordered properly (ie. the same way as
        # defined in benchmarks.json)
        newResultParamValues = tuple(v for (_, v) in benchmarkResult.argNameValuePairs)

        # Update the "params" lists with the new param settings for the new result.
        # Only add values that are not already present
        numExistingParamValues = len(existingParamValuesList)
        if numExistingParamValues == 0:
            for newParamValue in newResultParamValues:
                existingParamValuesList.append([newParamValue])
            results = [benchmarkResult.result]

        else:
            for i in range(numExistingParamValues):
                if newResultParamValues[i] not in existingParamValuesList[i]:
                    existingParamValuesList[i].append(newResultParamValues[i])

            # ASV uses the cartesian product of the param values for looking up
            # the result for a particular combination of param values.  For
            # example: "params": [ ["a"], ["b", "c"], ["d", "e"] results in:
            # [("a", "b", "d"), ("a", "b", "e"), ("a", "c", "d"), ("a", "c",
            # "e")] and each combination of param values has a result, with the
            # results for the corresponding param values in the same order.  If
            # a result for a set of param values DNE, use None.

            # store existing results in map based on cartesian product of all
            # current params.
            paramsCartProd = list(itertools.product(*existingParamValuesList))
            # Assume there is an equal number of results for cartProd values
            # (some will be None)
            paramsResultMap = dict(zip(paramsCartProd, existingResultValueList))

            # Add the new result
            paramsResultMap[newResultParamValues] = benchmarkResult.result

            # Re-compute the cartesian product of all param values now that the
            # new values are added. Use this to determine where to place the new
            # result in the result list.
            results = []
            for paramVals in itertools.product(*existingParamValuesList):
                results.append(paramsResultMap.get(paramVals))

        resultDict["params"] = existingParamValuesList
        resultDict["result"] = results

        d["commit_hash"] = benchmarkInfo.commitHash
        d["date"] = int(benchmarkInfo.commitTime)
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


    def __getResultsFilePath(self, benchmarkInfo):
        # The path to the resultsFile will be based on additional params present
        # in the benchmarkInfo obj.
        fileNameParts = [benchmarkInfo.commitHash,
                         "python%s" % benchmarkInfo.pythonVer,
                         "cuda%s" % benchmarkInfo.cudaVer,
                         benchmarkInfo.osType,
                        ]
        fileName = "-".join(fileNameParts) + ".json"
        return path.join(self.resultsDirPath,
                         benchmarkInfo.machineName,
                         fileName)


    def __loadJsonDictFromFile(self, jsonFile):
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
                except OSError as e:
                    print("Could not get file lock, ignoring. (OSError: %s)" % e)

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
            except OSError as e:
                print("Could not get file lock, ignoring. (OSError: %s)" % e)

            json.dump(jsonDict, fobj, indent=2)
