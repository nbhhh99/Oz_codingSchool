from fastapi import APIRouter, HTTPException, status


router = APIRouter(prefix="/practice_api", tags=["practice"])


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

@router.delete("/users/{user_id}", status_code=status.HTTP_200_OK)
async def delete_user(user_id: int):
    for index, user in enumerate(user_list):
        if user["id"] == user_id:
            deleted_user = user_list.pop(index)

            return {
                "message": "회원 정보가 삭제되었습니다.",
                "deleted_user": deleted_user,
            }

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Not Found",
    )