# Seacargos
Sea cargos aggregator web application.
Current app version is being developed to aggregate ONE (Ocean Network Express) 
container shippings.

## Technology stack
- Python 3.10
- Flask 2.2
- WTForms 3.0
- Pymongo 4.3
- Gunicorn 20.1
- Nginx 1.21.3
- MongoDB 5.0
- Mongo-express

## Web application
Seacargos web application is created with Flask framework and may be helpfull 
in tracking container shippings. It has simple user and administrator web 
interfaces. Python ETL scripts get and update data from container shipping web 
sites and store them in MongoDB database. Python ETL scripts can be run by user 
manually via web interface and/or scheduled with any simple tool like Linux 
crontab. 

## Web application infrastructure
The web application is designed to be deployed in four Docker containers:
- monogo - MongoDB container
- mongo-express - web interface container to access database
- wep - container with seacargos web application
- nginx - container with nginx server


## How to install and deploy
Docker should be already installed on local host before deployment.
1. Clone the repository.
```sh
# Run git clone command
git clone https://github.com/evgeny81d/seacargos.git
```

2. Create `.env` file with secrets in projects `infra/` directory.
Replace placeholders `<...>` with your secret data. Two first users will be 
created automatically during database initialization: simple user and site 
 administrator. Please use their credentials for first login. 
```sh
# Filepath: seacargos/infra/.env
# Mongo container variables
MONGO_INITDB_ROOT_USERNAME=<name>
MONGO_INITDB_ROOT_PASSWORD=<password>
# Mongo-express container variables
ME_CONFIG_MONGODB_ADMINUSERNAME=<name>
ME_CONFIG_MONGODB_ADMINPASSWORD=<password>
ME_CONFIG_MONGODB_URL=mongodb://<name>:<password>@mongo:27017/
# Web container variables to configure flask application
FLASK_DB_FRONTEND_URI=mongodb://<name>:<password>@mongo:27017/
FLASK_DB_NAME=production
FLASK_SECRET_KEY=<your strong secret key>
FLASK_ADMIN_NAME=<admin user name>
FLASK_ADMIN_PASSWORD=<admin user password>
FLASK_USER_NAME=<user name>
FLASK_USER_PASSWORD=<user password>
# Web container variables for ETL pipelines
ONE_URL=https://ecomm.one-line.com/ecom/CUP_HOM_3301GS.do
```

3. Deploy
```sh
# Go to the projects infra directory
cd seacargos/infra

# Start docker containers (web container will be build from source code)
sudo docker-compose up -d --build
```

## Finally the web application is ready for use

http://127.0.0.1 - web application login page

http://127.0.0.1:8081 - mongo-express database web interface


## How to stop containers
```sh
# Stop and persist the data
sudo docker-compose stop

# Start containers again
sudo docker-compose start

# Stop with deleting all data
sudo docker-compose down -v
```

## Security notice
The above instructions how to install and deploy the project have only 
demonstration purpose and can be used on local host.

If you would like to deploy the project on a web server, please read the 
[documentation](https://flask.palletsprojects.com/en/2.0.x/deploying/).

[Mongo-express](https://hub.docker.com/_/mongo-express) should only be used for 
development purpose as database web interface. It should be removed from 
`docker-compose.yaml` in production.
