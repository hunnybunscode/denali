#!/bin/bash
    uploadedfile=$1
    schemafile=$2
    DATA="{`apache-daffodil-3.5.0-bin/bin/daffodil parse -s $schemafile $uploadedfile`}"
    RESPONSE="{ XML: $DATA\"}"
    echo $RESPONSE
