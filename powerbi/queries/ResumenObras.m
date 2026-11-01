let
    Source = fnObraPulseGet("obras", null),
    Tabla = if List.IsEmpty(Source) then #table({}, {}) else Table.FromRecords(Source),
    Tipos = Table.TransformColumnTypes(Tabla, {
        {"obra", type text}, {"tareas", Int64.Type}, {"pv", type number}, {"ev", type number},
        {"valor_perdido", type number}, {"hh_perdidas", type number}, {"hh_totales", type number},
        {"ppc", type number}, {"spi", type number}, {"pct_hh_perdidas", type number}
    }, "es-AR")
in
    Tipos
