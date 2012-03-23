#!/bin/bash

# this uploads all the users listed in gmailusers.txt

started=`date`

cat gmailusers.txt | while read line; do 
    user=`echo $line | sed 's/@/ /g' | awk '{print $1}'`
    echo upload.py -e $line -u $user
    ./upload.py -e $line -u $user
done

echo started at $started, ended at `date`
