# app/apis/practice_apis.py
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/practice_api")

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


@router.get("/users/{user_id}")
def get_user(user_id: str):
    try:
        user_id_int = int(user_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="유효한 id가 아닙니다.")

    for user in user_list:
        if user["id"] == user_id_int:
            return {
                "id": user["id"],
                "name": user["name"],
                "age": user["age"],
                "email": user["email"]
            }

    raise HTTPException(status_code=404, detail="해당 id의 회원을 찾을 수 없습니다.")
