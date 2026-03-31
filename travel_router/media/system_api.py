from ..system_apis import all_resume_seconds, jellyfin_image_url, jellyfin_items, jellyfin_views


def media_payload(search_term: str | None, parent_id: str | None) -> dict:
    local_resume = all_resume_seconds()
    if not parent_id and not search_term:
        items = jellyfin_views()
    else:
        items = jellyfin_items(parent_id=parent_id, search_term=search_term)

    if items.get("ok"):
        normalized_items = []
        for item in items["data"].get("Items", []):
            item["LocalResumeSeconds"] = int(local_resume.get(item.get("Id", ""), 0) or 0)
            item["image_url"] = jellyfin_image_url(item["Id"])
            normalized_items.append(item)
        items["data"]["Items"] = normalized_items

    return {
        "search_term": search_term or "",
        "parent_id": parent_id or "",
        "items": items,
    }
