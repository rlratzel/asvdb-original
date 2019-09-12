# ASVDb

Python interface to a ASV "database", as described [here](https://asv.readthedocs.io/en/stable/dev.html?highlight=%24results_dir#benchmark-suite-layout-and-file-formats).

NOTE: This is currently a "write-only" interface.

Example:

Add a benchmark result to the "database"
```
import platform
import psutil
from asvdb import utils, BenchmarkInfo, BenchmarkResult, ASVDb

# Create a BenchmarkInfo object describing the benchmarking environment.
# This can/should be reused when adding multiple results from the same environment.

uname = platform.uname()
(commitHash, commitTime) = utils.getCommitInfo()  # gets commit info from CWD by default

bInfo = BenchmarkInfo(machineName=uname.machine,
                      cudaVer="10.0",
                      osType="%s %s" % (uname.system, uname.release),
                      pythonVer=platform.python_version(),
                      commitHash=commitHash,
                      commitTime=commitTime,
                      gpuType="n/a",
                      cpuType=uname.processor,
                      arch=uname.machine,
                      ram="%d" % psutil.virtual_memory().total)

# Create result objects for each benchmark result. Each result object
# represents a result from a single benchmark run, including any specific
# parameter settings the benchmark used (ie. arg values to a benchmark function)
bResult1 = BenchmarkResult(funcName="myAlgoBenchmarkFunc",
                           argNameValuePairs=[
                              ("iterations", 100),
                              ("dataset", "januaryData")
                           ],
                           result=301.23)

bResult2 = BenchmarkResult(funcName="myAlgoBenchmarkFunc",
                           argNameValuePairs=[
                              ("iterations", 100),
                              ("dataset", "februaryData")
                           ],
                           result=287.93)

# Create an interface to an ASV "database" to write the results to.
(repo, branch) = utils.getRepoInfo()  # gets repo info from CWD by default

db = ASVDb(dbDir="/datasets/benchmarks/asv",
           repo=repo,
           branches=[branch])

# Each addResult() call adds the result and creates/updates all JSON files
db.addResult(bInfo, bResult1)
db.addResult(bInfo, bResult2)
```
This results in a `asv.conf.json` file in `/datasets/benchmarks/asv` containing:
```
{
  "results_dir": "results",
  "html_dir": "html",
  "repo": <the repo URL>,
  "branches": [
    <the branch name>
  ],
  "version": 1.0
}
```
and `results/benchmarks.json` containing:
```
{
  "myAlgoBenchmarkFunc": {
    "code": "myAlgoBenchmarkFunc",
    "name": "myAlgoBenchmarkFunc",
    "param_names": [
      "iterations",
      "dataset"
    ],
    "params": [
      [
        100,
        100
      ],
      [
        "januaryData",
        "februaryData"
      ]
    ],
    "timeout": 60,
    "type": "time",
    "unit": "seconds",
    "version": 2
  },
  "version": 2
}
```
a `<machine>/machine.json` file containing:
```
{
  "arch": "x86_64",
  "cpu": "x86_64",
  "gpu": "n/a",
  "cuda": "10.0",
  "machine": "x86_64",
  "os": "Linux 4.4.0-146-generic",
  "ram": "540955688960",
  "version": 1
}
```
and a `<machine>/<commit hash>.json` file containing:
```
{
  "params": {
    "gpu": "n/a",
    "cuda": "10.0",
    "machine": "x86_64",
    "os": "Linux 4.4.0-146-generic",
    "python": "3.7.1"
  },
  "requirements": {},
  "results": {
    "myAlgoBenchmarkFunc": {
      "params": [
        [
          100,
          100
        ],
        [
          "januaryData",
          "februaryData"
        ]
      ],
      "result": [
        301.23,
        287.93
      ]
    }
  },
  "commit_hash": "c551640ca829c32f520771306acc2d177398b721",
  "date": "156812889600",
  "python": "3.7.1",
  "version": 1
}
```
