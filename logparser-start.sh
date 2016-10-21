#!/bin/sh

script_dir=$(dirname $0)
if [ $script_dir = '.' ]
then
    script_dir=$(pwd)
fi

cd $script_dir && /usr/bin/env python3 logparser.py
