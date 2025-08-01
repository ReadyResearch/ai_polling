library(tidyverse)
data <- readRDS('extracted_data/cleaned_polling_data.rds')
cat('Total records:', nrow(data), '\n')
cat('Records with valid dates:', sum(!is.na(data$Fieldwork_Date)), '\n')
cat('Date range:', as.character(min(data$Fieldwork_Date, na.rm = TRUE)), 'to', as.character(max(data$Fieldwork_Date, na.rm = TRUE)), '\n')