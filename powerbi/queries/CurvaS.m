let
    Source = fnObraPulseGet("curva-s", null),
    Tabla = if List.IsEmpty(Source) then #table({}, {}) else Table.FromRecords(Source),
    Tipos = Table.TransformColumnTypes(Tabla, {
        {"obra", type text}, {"fecha", type date}, {"pv", type number}, {"ev", type number},
        {"pv_acum", type number}, {"ev_acum", type number}
    }, "es-AR")
in
    Tipos
