import argparse
from os import path

import asvdb


def parseArgs(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", action="store_true",
                        help="Print the current verison of asvdb and exit.")
    parser.add_argument("--read-from", type=str, metavar="PATH",
                        help="Path to ASV db dir to read data from.")
    parser.add_argument("--list-keys", action="store_true",
                        help="List all keys found in the database to STDOUT.")
    parser.add_argument("--filter", metavar="EXPR", dest="cmds",
                        type=storeCmd("filter"), action="append",
                        help="Filter the current results based on the "
                        "evaluation of %(metavar)s.")
    parser.add_argument("--exec", metavar="EXPR", dest="cmds",
                        type=storeCmd("exec"), action="append",
                        help="Execute %(metavar)s on each of the current "
                        "results.")
    parser.add_argument("--print", metavar="PRINTEXPR", dest="cmds",
                        type=storeCmd("print"), action="append",
                        help="Evaluate %(metavar)s in a print() statement for "
                        "each of the current results.")
    parser.add_argument("--write-to", type=str, metavar="PATH",
                        help="Path to ASV db dir to write data to. %(metavar)s "
                        "is created if it does not exist. If not specified, "
                        "results are written to STDOUT.")

    return parser.parse_args(argv)


def storeCmd(cmdName):
    """
    Return a callable to be called by argparse that returns a tuple containing
    cmdName and the option given on the command line.
    """
    def callable(stringOpt):
        if not stringOpt:
            raise argparse.ArgumentTypeError("Cannot be empty")
        return (cmdName, stringOpt)
    return callable


def openAsvdbAtPath(dbDir, repo=None, branches=None,
                    projectName=None, commitUrl=None):
    """
    Either reads the ASV db at dbDir and creates a new db object, or creates a
    new db object and sets up the db at dbDir for (presumably) writing new
    results to.
    """
    db = asvdb.ASVDb(dbDir, repo=repo, branches=branches,
                     projectName=projectName, commitUrl=commitUrl)
    if path.isdir(dbDir):
        db.loadConfFile()
    else:
        db.updateConfFile()
    return db


def createNamespace(benchmarkInfo, benchmarkResult):
    """
    Creates a dictionary representing a namespace containing the member
    var/values on the benchmarkInfo and benchmarkResult passed in to eval/exec
    expressions in. This is usually used in place of locals() in calls to eval()
    or exec().
    """
    namespace = dict(benchmarkInfo.__dict__)
    namespace.update(benchmarkResult.__dict__)
    return namespace


def updateObjsFromNamespace(benchmarkInfo, benchmarkResult, namespace):
    """
    Update the benchmarkInfo and benchmarkResult objects passed in with the
    contents of the namespace dict. The objects are updated based on the key
    name (eg. a key of commitHash updates benchmarkInfo.commitHash since
    commitHash is a member of the BenchmarkInfo class). Any other keys that
    aren't members of either class end up updating the global namespace.
    """
    for attr in asvdb.BenchmarkInfoKeys:
        setattr(benchmarkInfo, attr, namespace.pop(attr))
    for attr in asvdb.BenchmarkResultKeys:
        setattr(benchmarkResult, attr, namespace.pop(attr))
    # All leftover vars in the namespace should be applied to the global
    # namespace. This allows exec commands to store intermediate values.
    globals().update(namespace)


def filterResults(resultTupleList, expr):
    """
    Return a new list of results contining objects that evaluate as True when
    the expression is applied to them.
    """
    newResultTupleList = []
    for (benchmarkInfo, benchmarkResults) in resultTupleList:
        resultsForInfo = []
        for resultObj in benchmarkResults:
            namespace = createNamespace(benchmarkInfo, resultObj)
            if eval(expr, globals(), namespace):
                resultsForInfo.append(resultObj)
        if resultsForInfo:
            newResultTupleList.append((benchmarkInfo, resultsForInfo))
    return newResultTupleList


def printResults(resultTupleList, expr):
    """
    Print the print expression for each result in the resultTupleList list.
    """
    for (benchmarkInfo, benchmarkResults) in resultTupleList:
        for resultObj in benchmarkResults:
            namespace = createNamespace(benchmarkInfo, resultObj)
            eval(f"print({expr})", globals(), namespace)
    return resultTupleList


def execResults(resultTupleList, code):
    """
    Run the code on each result in the list. This likely results in modified
    objects and possibly new variables in the global namespace.
    """
    for (benchmarkInfo, benchmarkResults) in resultTupleList:
        for resultObj in benchmarkResults:
            namespace = createNamespace(benchmarkInfo, resultObj)
            exec(code, globals(), namespace)
            updateObjsFromNamespace(benchmarkInfo, resultObj, namespace)
    return resultTupleList


def updateDb(dbObj, resultTupleList):
    """
    Write the results to the dbOj.
    """
    for (benchmarkInfo, benchmarkResults) in resultTupleList:
        for result in benchmarkResults:
            dbObj.addResult(benchmarkInfo, result)


def main():
    cmdMap = {"filter": filterResults,
              "print": printResults,
              "exec": execResults,
              }
    args = parseArgs()

    if args.version:
        print(asvdb.__version__)
        return

    if args.list_keys:
        for k in set.union(asvdb.BenchmarkInfoKeys, asvdb.BenchmarkResultKeys):
            print(k)

    else:
        if args.read_from is None:
            raise RuntimeError("--read-from must be specified")

        fromDb = openAsvdbAtPath(args.read_from)

        results = fromDb.getResults()
        for (cmd, expr) in args.cmds or []:
            results = cmdMap[cmd](results, expr)

        if args.write_to:
            toDb = openAsvdbAtPath(args.write_to,
                                   repo=fromDb.repo,
                                   branches=fromDb.branches,
                                   projectName=fromDb.projectName,
                                   commitUrl=fromDb.commitUrl)
            updateDb(toDb, results)


if __name__ == "__main__":
    main()
