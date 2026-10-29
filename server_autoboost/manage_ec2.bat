@echo off
setlocal

echo Connecting to AutoBoost on ubuntu@client.truewilly.com (Amazon Linux 2023 EC2)...
ssh -t ubuntu@client.truewilly.com "sudo autoboost"
