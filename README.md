# ASVDb

Python interface to a ASV "database", as described [here](https://asv.readthedocs.io/en/stable/dev.html?highlight=%24results_dir#benchmark-suite-layout-and-file-formats).

## Examples:

### Read results from the "database"
```
>>> import asvdb
>>> db = asvdb.ASVDb("/path/to/benchmarks/asv")
>>>
>>> results = db.getResults()  # Get a list of (BenchmarkInfo obj, [BenchmarkResult obj, ...]) tuples.
>>> len(results)
9
>>> firstResult = results[0]
>>> firstResult[0]
BenchmarkInfo(machineName='my_machine', cudaVer='9.2', osType='debian', pythonVer='3.6', commitHash='f6242e77bf32ed12c78ddb3f9a06321b2fd11806', commitTime=1589322352000, gpuType='Tesla V100-SXM2-32GB', cpuType='x86_64', arch='x86_64', ram='540954406912')
>>> len(firstResult[1])
132
>>> firstResult[1][0]
BenchmarkResult(funcName='bench_algos.bench_create_edgelist_time', result=0.46636209040880205, argNameValuePairs=[('csvFileName', '../datasets/csv/undirected/hollywood.csv')], unit='seconds')
>>>
```

### Add benchmark results to the "database"
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
