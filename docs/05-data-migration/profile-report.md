# Source Profile Report

- File: `library-export-20k.xlsx`
- Data rows: 20,000

| Column | Empty | Distinct | Values repeated | Cell types | Most common values |
|---|---|---|---|---|---|
| Accession No | 0 | 19,761 | 227 | str 20,000 | AC#35; AC#32; AC#01 |
| Barcode | 0 | 19,800 | 198 | str 20,000 | BC00100176; BC00111898; BC00100013 |
| Title | 95 | 19,341 | 551 | str 19,905 | Inverse Object-Oriented Succes; Universal Full-Range Website; Self-Enabling Transitional Int |
| Author | 0 | 18,930 | 1,032 | str 20,000 | Abhiram Mistry; Yuvraj Dutta; Balvan Devan |
| ISBN | 0 | 19,800 | 198 | str 19,774, int 226 | 9789027716705; 9783904620703; 9784210205394 |
| Publisher | 0 | 15,944 | 2,159 | str 20,000 | Kala Inc; Dara Group; Dara PLC |
| Year | 0 | 67 | 67 | int 20,000 | 1989; 2009; 1991 |
| Edition | 4,970 | 3 | 3 | str 15,030 | 2nd; 1st; 3rd |
| Subjects | 0 | 12,768 | 889 | str 20,000 | nam; magni; cum |
| Call No | 0 | 19,788 | 210 | str 20,000 | 388.40 DUT; 361.39 DAY; 133.33 TRI |
| Shelf | 0 | 8 | 8 | str 20,000 | A-01; D-02; C-01 |
| Item Type | 0 | 5 | 5 | str 20,000 | lending; reference; LENDING |
| Price | 0 | 19,357 | 628 | float 19,792, int 208 | 753.75; 3927.25; 2764.69 |
| Acquired On | 0 | 8,173 | 5,762 | datetime 19,768, int 232 | 2009-07-03 00:00:00; 2003-01-26 00:00:00; 2023-05-04 00:00:00 |

Observations to act on in the validation rules:
- Columns with mixed cell types (for example ISBN stored as both text and number, or dates stored as Excel serial numbers) are normalised before validation.
- Repeated accession numbers indicate exact duplicates; they are excluded and reported.
- Empty mandatory cells (title, accession number) are rejected with a reason code.

