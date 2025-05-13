
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs


sudo -u postgres psql
CREATE DATABASE carbon;
CREATE USER carbon_user WITH PASSWORD 'securepassword123';
GRANT ALL PRIVILEGES ON DATABASE carbon TO carbon_user;

GRANT ALL ON SCHEMA public TO carbon_user;
ALTER DATABASE carbon OWNER TO carbon_user;
\q

psql -U carbon_user -d carbon -h localhost -p 5433 -W

frontend:

npx create-vite@latest frontend --template react
cd frontend
npm install

npm install @mui/material @emotion/react @emotion/styled react-router-dom react-i18next
npm install --save-dev eslint prettier
npm install @mui/icons-material
npm install @mui/material @mui/icons-material
npm install recharts
npm run dev

backend:

python3 -m venv venv
source venv/bin/activate

pip install django djangorestframework psycopg2-binary djangorestframework-simplejwt django-cors-headers

django-admin startproject backend .
cd backend/

edit backend/settings.py: 

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'carbon',
        'USER': 'carbon_user',
        'PASSWORD': 'securepassword123',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

python manage.py makemigrations
python manage.py migrate

test JWT:

curl -X POST http://127.0.0.1:8000/api/token/ -d "username=ahmed&password=Cup4PWS_101"
curl -X POST http://localhost:8000/api/token/ -H "Content-Type: application/json" \
  -d '{"username": "admin1", "password": "T$t12345"}'

users passwd: T$t12345

populate some data:
python manage.py populate_demo_users

python manage.py makemigrations accounts
python manage.py migrate accounts
python manage.py makemigrations core
python manage.py migrate core
python manage.py migrate
python manage.py createsuperuser

python manage.py runserver
npm run dev

----

Deploy on docker ubuntu on :/opt/carbon

- Clone Repository
sudo mkdir -p /opt/carbon
sudo chown $USER:$USER /opt/carbon
cd /opt/carbon
git clone https://github.com/ahmedse/carbon.git .

vi /etc/postgresql/<version>/main/pg_hba.conf
host    all             all             127.0.0.1/32            md5
sudo systemctl restart postgresql
psql -U carbon_user -d carbon -h localhost -p 5433 -W
securepassword123
\dt

docker-compose up --build
docker-compose exec backend python manage.py migrate
docker-compose exec backend python manage.py createsuperuser

vi /etc/nginx/conf.d/carbon.conf

Ensure ports 5173 and 8000 are NOT open to the public
use the host's PostgreSQL, set in your .env and settings:
DB_HOST=host.docker.internal

docker-compose up -d --build backend

docker-compose logs backend

sudo vi /etc/postgresql/16/main/pg_hba.conf
sudo vi /etc/postgresql/16/main/postgresql.conf
sudo systemctl restart postgresql


docker-compose exec backend bash
apt-get update && apt-get install -y postgresql-client
psql -U carbon_user -d carbon -h host.docker.internal -p 5433 -W

docker-compose down
docker-compose up -d --build

python manage.py dbshell