import json


def save_admins(admins_list):
    with open("admins.json", "w", encoding="utf-8") as file:
        json.dump(admins_list, file, ensure_ascii=False, indent=4)


def save_added_goods(added_good):
    try:
        with open("added_goods.json", "r", encoding="utf-8") as file:
            existing_goods = json.load(file)
    except FileNotFoundError:
        existing_goods = []
    existing_goods.append(added_good)
    
    with open("added_goods.json", "w", encoding="utf-8") as file:
        json.dump(existing_goods, file, ensure_ascii=False, indent=4)


def get_and_remove_first_five():
    try:
        with open("added_goods.json", "r", encoding="utf-8") as file:
            goods = json.load(file)
    except FileNotFoundError:
        return []
    first_five = goods[:5]
    remaining_goods = goods[5:]

    with open("added_goods.json", "w", encoding="utf-8") as file:
        json.dump(remaining_goods, file, ensure_ascii=False, indent=4)

    return first_five
