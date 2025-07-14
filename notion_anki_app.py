def fetch_from_notion(token, db_id):
    notion = Client(auth=token)
    cards = []
    start_cursor = None
    while True:
        query_params = {"database_id": db_id}
        if start_cursor:
            query_params["start_cursor"] = start_cursor
        response = notion.databases.query(**query_params)
        data = response['results']
        for r in data:
            props = r['properties']
            try:
                q = props['Pergunta']['title'][0]['text']['content']
                a = props['Resposta']['rich_text'][0]['text']['content']
                cards.append((q, a))
            except:
                continue
        if not response.get('has_more'):
            break
        start_cursor = response.get('next_cursor')
    return cards
