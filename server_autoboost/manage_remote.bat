@echo off
setlocal

echo Connecting to AutoBoost on ubuntu@client.truewilly.com...
ssh -t ubuntu@client.truewilly.com "sudo autoboost"
