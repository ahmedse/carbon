python manage.py shell

from accounts.models import User
u = User.objects.get(username='admin1')
print(u.is_active)
print(u.check_password('T$t12345'))

curl -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin1","password":"T$t12345"}'

# frontend
console.log("[Login] Submitting login for:", username);