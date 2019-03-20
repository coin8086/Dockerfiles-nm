git checkout master
git pull

docker pull evancui/nodemanager:nmexecbase
docker pull evancui/nodemanager:nmbuildbase
docker build -t evancui/nodemanager:latest -f Dockerfile-nodemanager-v1 .
docker push evancui/nodemanager:latest

[ -d "./out/" ] && rm -rf ./out
mkdir ./out
cd out
mkdir opt
mkdir publish

docker rm -fv nmcopy || true
docker pull evancui/nodemanager:latest
docker run -d --name nmcopy -it --entrypoint bash evancui/nodemanager
docker cp nmcopy:/app/. ./opt/
docker cp nmcopy:/opt/. ./opt/
docker cp nmcopy:/publish/. ./publish

docker rm -fv nmcopy

cd opt
zip -r ../../HpcAcmAgent-1.0.$BUILD_NUMBER.0.zip *
