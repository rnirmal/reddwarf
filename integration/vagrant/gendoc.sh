#!/bin/bash

current_dir=$(pwd)

cd ../../apidocs
mvn clean
mvn generate-sources

cd $current_dir

