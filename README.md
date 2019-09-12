# ASVDb

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

bResult1 = BenchmarkResult(funcName="myAlgorithm",
                           argNameValuePairs=[
                              ("iterations", 100),
                              ("dataset", "januaryData")
                           ],
                           result=301.23)
bResult2 = BenchmarkResult(funcName="myAlgorithm",
                           argNameValuePairs=[
                              ("iterations", 100),
                              ("dataset", "februaryData")
                           ],
                           result=287.93)

# Create an interface to an ASV "database" to write the result to.

(repo, branch) = utils.getRepoInfo()  # gets repo info from CWD by default

db = ASVDb(dbDir="/datasets/benchmarks/asv",
           repo=repo,
           branches=[branch])

# Each addresult() call adds the result and creates/updates all JSON files
db.addResult(bInfo, bResult1)
db.addResult(bInfo, bResult2)
```
