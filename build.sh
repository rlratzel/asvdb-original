#!/bin/bash

set -e

UPLOAD_FILE=`conda build ./conda --output`
conda build ./conda
anaconda upload ${UPLOAD_FILE}
