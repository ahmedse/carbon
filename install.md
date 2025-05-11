
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs


sudo -u postgres psql
CREATE DATABASE carbon;
CREATE USER carbon_user WITH PASSWORD 'securepassword123';
GRANT ALL PRIVILEGES ON DATABASE carbon TO carbon_user;

GRANT ALL ON SCHEMA public TO carbon_user;
ALTER DATABASE carbon OWNER TO carbon_user;
\q

psql -U carbon_user -d carbon -h localhost -W

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
docker-compose up --build

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