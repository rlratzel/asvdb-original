from os import path
import tempfile
import json
import threading
import time

import pytest

datasetName = "dolphins.csv"
algoRunResults = [('loadDataFile', 3.2228727098554373),
                  ('createGraph', 3.00713360495865345),
                  ('pagerank', 3.00899268127977848),
                  ('bfs', 3.004273353144526482),
                  ('sssp', 3.004624705761671066),
                  ('jaccard', 3.0025573652237653732),
                  ('louvain', 3.32631026208400726),
                  ('weakly_connected_components', 3.0034315641969442368),
                  ('overlap', 3.002147899940609932),
                  ('triangles', 3.2544921860098839),
                  ('spectralBalancedCutClustering', 3.03329935669898987),
                  ('spectralModularityMaximizationClustering', 3.011258183047175407),
                  ('renumber', 3.001620553433895111),
                  ('view_adj_list', 3.000927431508898735),
                  ('degree', 3.0016251634806394577),
                  ('degrees', None)]


@pytest.mark.skip(reason="Not written yet")
def test_addResult():
    """
    FIXME: This is not a test yet, use example code below to create 1 or more tests
    """
    return

    (commitHash, commitTime) = getCommitInfo()
    (repo, branch) = getRepoInfo()

    db = ASVDb(asvDir, repo, [branch])

    uname = platform.uname()

    bInfo = BenchmarkInfo(machineName=machineName or uname.machine,
                          cudaVer=cudaVer or "n/a",
                          osType=osType or "%s %s" % (uname.system, uname.release),
                          pythonVer=pythonVer or platform.python_version(),
                          commitHash=commitHash,
                          commitTime=commitTime,
                          gpuType="n/a",
                          cpuType=uname.processor,
                          arch=uname.machine,
                          ram="%d" % psutil.virtual_memory().total)

    for (algoName, exeTime) in algoRunResults:
        bResult = BenchmarkResult(funcName=algoName,
                                  argNameValuePairs=[("dataset", datasetName)],
                                  result=exeTime)
        db.addResult(bInfo, bResult)


def test_newBranch():

    from asvdb import ASVDb

    asvDir = tempfile.TemporaryDirectory()
    repo = "somerepo"
    branch1 = "branch1"
    branch2 = "branch2"

    db1 = ASVDb(asvDir.name, repo, [branch1])
    db1.updateConfFile()
    db2 = ASVDb(asvDir.name, repo, [branch2])
    db2.updateConfFile()

    confFile = path.join(asvDir.name, "asv.conf.json")
    with open(confFile) as fobj:
        j = json.load(fobj)
        branches = j["branches"]

    assert branches == [branch1, branch2]

    asvDir.cleanup()


def test_gitExtension():

    from asvdb import ASVDb

    asvDir = tempfile.TemporaryDirectory()
    repo = "somerepo"
    branch1 = "branch1"

    db1 = ASVDb(asvDir.name, repo, [branch1])
    db1.updateConfFile()

    confFile = path.join(asvDir.name, "asv.conf.json")
    with open(confFile) as fobj:
        j = json.load(fobj)
        repo = j["repo"]

    assert repo.endswith(".git")

    asvDir.cleanup()


def test_concurrency():

    from asvdb import ASVDb, BenchmarkInfo, BenchmarkResult

    asvDir = tempfile.TemporaryDirectory()
    repo = "somerepo"
    branch1 = "branch1"

    db1 = ASVDb(asvDir.name, repo, [branch1])
    db2 = ASVDb(asvDir.name, repo, [branch1])
    db3 = ASVDb(asvDir.name, repo, [branch1])
    # Use the writeDelay member var to insert a delay during write to properly
    # test collisions by making writes slow.
    db1.writeDelay = 10
    db2.writeDelay = 10

    bInfo = BenchmarkInfo()
    bResult1 = BenchmarkResult(funcName="somebenchmark1", result=43)
    bResult2 = BenchmarkResult(funcName="somebenchmark2", result=43)
    bResult3 = BenchmarkResult(funcName="somebenchmark3", result=43)

    # db1 or db2 should be actively writing the result (because the writeDelay is long)
    # and db3 should be blocked.
    t1 = threading.Thread(target=db1.addResult, args=(bInfo, bResult1))
    t2 = threading.Thread(target=db2.addResult, args=(bInfo, bResult2))
    t3 = threading.Thread(target=db3.addResult, args=(bInfo, bResult3))
    t1.start()
    t2.start()
    time.sleep(0.5)  # ensure t3 tries to write last
    t3.start()

    # Check that db3 is blocked - if locking wasn't working, it would have
    # finished since it has no writeDelay.
    t3.join(timeout=0.5)
    assert t3.is_alive() is True

    # Cancel db1 and db2, allowing db3 to write and finish
    db1.cancelWrite = True
    db2.cancelWrite = True
    t3.join(timeout=11)
    assert t3.is_alive() is False
    t1.join()
    t2.join()
    t3.join()

    # Check that db3 wrote its result
    with open(path.join(asvDir.name, "results", "benchmarks.json")) as fobj:
        jo = json.load(fobj)
        assert "somebenchmark3" in jo
        #print(jo)

    asvDir.cleanup()
