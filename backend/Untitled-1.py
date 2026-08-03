from database import *

init_database()

print("Database created!")

add_user(123456789, "yaroslav")

user = get_user(123456789)

print(dict(user))
