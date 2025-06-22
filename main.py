from pydantic import BaseModel

import pymupdf


class BBox(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float


class Word(BaseModel):
    text: str
    bbox: BBox

    line: int | None = None
    column: int | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "Word":
        return Word(text=data["text"], bbox=BBox(x0=data["bbox"][0], y0=data["bbox"][1], x1=data["bbox"][2], y1=data["bbox"][3]))
    
    def text_lower(self) -> str:
        return self.text.strip().lower()


class Line(BaseModel):
    words: list[Word]


    def __init__(self, words: list[Word]) -> None:
        super().__init__(words=sorted(words, key=lambda x: x.bbox.x0))
    

    def as_key_value_pairs(self) -> dict[str, str]:
        result = {}

        index = 0

        # Parse the line until the last word is reached
        # TODO: add support for multi-word keys/values
        while index < len(self.words):
            current_word = self.words[index].text_lower()
            next_word = self.words[index + 1].text_lower() if index + 1 < len(self.words) else ""

            if current_word.endswith(":"):
                result[current_word[:-1]] = next_word
                # Next word is already parsed, so we skip it
                index += 1
            
            index += 1

        return result
    

    def __str__(self) -> str:
        return " | ".join([word.text for word in self.words])



class Column(BaseModel):
    """
    A column is a list of lines that are close enough by their x0 coordinate to be in the same column.
    """

    words: list[Word]


    def __str__(self) -> str:
        text = ""
        current_line = 0

        for word in self.words:
            if word.line != current_line:
                text += "\n"
                current_line = word.line
            text += word.text + " "

        return text


class Page(BaseModel):

    words: list[Word]
    epsilon: float

    lines: list[Line] = []
    columns: list[Column] = []
    

    def __init__(self, words: list[Word], epsilon: float = 5) -> None:
        # Call parent __init__ first to properly initialize Pydantic fields
        super().__init__(words=words, epsilon=epsilon)
        
        # Sort by y0 to get the correct order of lines, then by x0 to get the correct order of words in the lines
        self.words = sorted(words, key=lambda w: (w.bbox.y0, w.bbox.x0))

        # Group words into lines
        lines: list[list[Word]] = []
        
        for word in self.words:
            placed = False
            for line_idx, line in enumerate(lines):
                # Group tokens into lines if they are close enough
                if abs(line[0].bbox.y0 - word.bbox.y0) < self.epsilon:
                    line.append(word)
                    word.line = line_idx
                    placed = True
                    break
            if not placed:
                word.line = len(lines)
                lines.append([word])


        # Assign column number to words if possible, based on the X0 proximity of the words
        # TODO: refactor to reduce code duplication. 
        columns: list[list[Word]] = []

        for word in self.words:
            placed = False
            for col_idx, column in enumerate(columns):
                if abs(column[0].bbox.x0 - word.bbox.x0) < self.epsilon:
                    column.append(word)
                    word.column = col_idx
                    placed = True
                    break
            if not placed:
                word.column = len(columns)
                columns.append([word])

        # Dissolve single-element columns and reassign to previous column
        for col_idx in range(len(columns) - 1, 0, -1):  # Start from last column, skip first
            if len(columns[col_idx]) == 1:
                # Reassign the word to the previous column
                word = columns[col_idx][0]
                word.column = col_idx - 1
                columns[col_idx - 1].append(word)
                # Remove the single-element column
                columns.pop(col_idx)

        # Update column numbers after dissolving
        for col_idx, column in enumerate(columns):
            for word in column:
                word.column = col_idx

        self.lines = [Line(words=line) for line in lines]
        self.columns = [Column(words=column) for column in columns]


    def __str__(self) -> str:
        return "\n".join([str(line) for line in self.lines])
    

    def as_columns(self) -> str:
        return "\n------------\n".join([str(column) for column in self.columns])



class Document(BaseModel):
    pages: list[Page]


    def __str__(self) -> str:
        return "\nNEW PAGE\n".join([str(page) for page in self.pages])
    

    def as_columns(self) -> str:
        return "\nNEW PAGE\n".join([str(page.as_columns()) for page in self.pages])



def main():
    document = pymupdf.open("rpt-scaninvoices.jpg")

    pages: list[Page] = []

    for page in document:
        words: list[Word] = []
        page_text = page.get_textpage_ocr()

        # (x0, y0, x1, y1, "word", block_no, line_no, word_no)
        page_words = page_text.extractWORDS()

        for word in page_words:
            words.append(Word(text=word[4], bbox=BBox(x0=word[0], y0=word[1], x1=word[2], y1=word[3])))

        pages.append(Page(words=words))

    document = Document(pages=pages)

    print(document.as_columns())



if __name__ == "__main__":
    main()
