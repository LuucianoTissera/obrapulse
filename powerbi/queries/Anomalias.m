let
    Source = fnObraPulseGet("anomalies", null),
    Tabla = if List.IsEmpty(Source) then #table({}, {}) else Table.FromRecords(Source),
    Tipos = Table.TransformColumnTypes(Tabla, {
        {"obra", type text}, {"causa_dominante", type text}
    }, "es-AR")
in
    Tipos
