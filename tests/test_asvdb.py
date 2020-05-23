from os import path
import tempfile
import json
import threading

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
    db2 = ASVDb(asvDir.name, repo, [branch2])

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

    # Use the writeDelay arg to insert a delay during write to properly test
    # collisions by making writes slow.
    db1 = ASVDb(asvDir.name, repo, [branch1], writeDelay=6)
    db2 = ASVDb(asvDir.name, repo, [branch1])

    bInfo = BenchmarkInfo()
    bResult = BenchmarkResult(funcName="somebenchmark", result=43)

    # db1 should be actively writing the result (because the writeDelay is long)
    # and db2 should be blocked.  Wait for db2 in a thread, and if it returned
    # (theb thread is no longer alive) the test was a failure.
    t1 = threading.Thread(target=db1.addResult, args=(bInfo, bResult))
    t2 = threading.Thread(target=db2.addResult, args=(bInfo, bResult))
    t1.start()
    t2.start()
    t2.join(timeout=1)
    assert t2.is_alive() is True
    db1.doWriteOperations = False
    db2.doWriteOperations = False
    t1.join()
    t2.join()
    asvDir.cleanup()
