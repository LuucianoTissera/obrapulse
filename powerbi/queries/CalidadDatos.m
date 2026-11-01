let
    Source = fnObraPulseGet("calidad-datos", null),
    Plano = Record.RemoveFields(Source, {"ultima_corrida"}, MissingField.Ignore),
    Tabla = Record.ToTable(Plano),
    Renombradas = Table.RenameColumns(Tabla, {{"Name", "indicador"}, {"Value", "valor"}})
in
    Renombradas
