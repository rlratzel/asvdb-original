#!/bin/bash

conda build ./conda
anaconda upload /home/nfs/rratzel/anaconda3/conda-bld/linux-64/asvdb-0.1.1dev0-py37_0.tar.bz2 
