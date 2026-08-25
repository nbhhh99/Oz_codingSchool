# app/apis/practice_apis.py
user_list = [
	{
		"id": 1,
		"name": "홍길동",
		"age": 24,
		"email": "gildong24@example.com",
		"password": "Password1234!!"
	},
	{
		"id": 2,
		"name": "장문복",
		"age": 21,
		"email": "moonluck12@example.com",
		"password": "Check1321!"
	},
	{
		"id": 3,
		"name": "임우진",
		"age": 31,
		"email": "limousine33@example.com",
		"password": "lwsPAssword12@"
	}
]
<<<<<<< Updated upstream
=======


class UserRegisterRequest(BaseModel):
    name: str
    age: int
    email: str
    password: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if not (2 <= len(v) <= 10):
            raise ValueError("이름은 최소 2자, 최대 10자여야 합니다.")
        return v

    @field_validator("age")
    @classmethod
    def validate_age(cls, v):
        if v < 14:
            raise ValueError("나이는 최소 14세 이상이어야 합니다.")
        return v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        if len(v) > 30:
            raise ValueError("이메일은 최대 30자까지 가능합니다.")
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(pattern, v):
            raise ValueError("올바른 이메일 형식이 아닙니다.")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if not (8 <= len(v) <= 20):
            raise ValueError("비밀번호는 최소 8자, 최대 20자여야 합니다.")
        if not re.search(r"[A-Z]", v):
            raise ValueError("비밀번호에 대문자가 1개 이상 포함되어야 합니다.")
        if not re.search(r"[a-z]", v):
            raise ValueError("비밀번호에 소문자가 1개 이상 포함되어야 합니다.")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError("비밀번호에 특수문자가 1개 이상 포함되어야 합니다.")
        return v


@router.post("/practice_api/users", summary="회원 등록 API")
def register_user_handler(body: UserRegisterRequest):
    for user in user_list:
        if user["email"] == body.email:
            raise HTTPException(status_code=400, detail="이미 사용 중인 이메일입니다.")

    new_id = max(user["id"] for user in user_list) + 1 if user_list else 1

    new_user = {
        "id": new_id,
        "name": body.name,
        "age": body.age,
        "email": body.email,
        "password": body.password,
    }
    user_list.append(new_user)

    return new_user

@router.get("/practice_api/users", summary="회원 목록 조회 API")
def get_users_handler():
    return [
        {"id": u["id"], "name": u["name"], "age": u["age"], "email": u["email"]}
        for u in user_list
    ]
>>>>>>> Stashed changes
