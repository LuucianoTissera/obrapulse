// Función común para consultar la API REST de ObraPulse.
// Crear parámetros Power Query: pBaseUrl (texto) y pApiKey (texto; vacío si no se usa API_KEY).
(relativePath as text, optional query as nullable record) as any =>
let
    ApiKey = try Text.Trim(pApiKey) otherwise "",
    Headers = if ApiKey = "" then
        [Accept = "application/json"]
    else
        [Accept = "application/json", #"X-API-Key" = ApiKey],
    Response = Json.Document(
        Web.Contents(
            Text.TrimEnd(pBaseUrl, "/") & "/",
            [
                RelativePath = relativePath,
                Query = if query = null then [] else query,
                Headers = Headers,
                Timeout = #duration(0, 0, 2, 0)
            ]
        )
    )
in
    Response
