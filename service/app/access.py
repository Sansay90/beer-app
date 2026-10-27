"""Роли и права — в одном месте; интерфейс только прячет недоступные кнопки, решает сервис.

Гость — без входа; пользователь и администратор — users.role.

| что можно                                                        | гость | пользователь | админ |
|------------------------------------------------------------------|:-----:|:------------:|:-----:|
| смотреть опубликованные рецепты и их фото                        |  да   |      да      |  да   |
| свои рецепты: создать, править, удалить, добавить фото           |       |      да      |  да   |
| опубликовать свой рецепт (почта подтверждена)                    |       |      да      |  да   |
| своя пивоварня, варки, уведомления                               |       |      да      |  да   |
| снять с публикации или удалить чужой опубликованный рецепт, фото |       |              |  да   |
| пользователи и их роли                                           |       |              |  да   |

Чужие личные рецепты не видит никто, администратор тоже: это частные данные.
"""
USER, ADMIN = "user", "admin"
ROLES = (USER, ADMIN)
PRIVATE, PUBLIC = "private", "public"
VISIBILITIES = (PRIVATE, PUBLIC)


def is_admin(user):
    return user is not None and user.role == ADMIN


def can_view(user, recipe):
    return recipe.visibility == PUBLIC or (user is not None and recipe.user_id == user.id)


def can_edit(user, recipe):
    return user is not None and recipe.user_id == user.id


def can_moderate(user, recipe):
    """Чужой опубликованный рецепт: снять с публикации, удалить, убрать фото."""
    return is_admin(user) and recipe.visibility == PUBLIC and recipe.user_id != user.id


def can_publish(user):
    return user is not None and user.email_verified_at is not None
