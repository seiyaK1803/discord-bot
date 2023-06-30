## Docker build
Takes the Dockerfile and creates an Docker image
`docker build <Dockerfile-directory>`

For reliable acces to the image, you can tag it with the '-t' flag
`docker build -t <image-name> <Dockerfile-directory>`

### Best practices
Typically docker tags consist of the repositories name followed by a versioning "-t <repo>:<version>" where version can be 'latest'

## Docker run
