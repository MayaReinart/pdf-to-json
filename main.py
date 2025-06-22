from pydantic import BaseModel

import pymupdf
from sklearn.cluster import DBSCAN

import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import numpy as np


class BBox(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float

    def center(self) -> tuple[float, float]:
        return (self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2


class Word(BaseModel):
    text: str
    bbox: BBox
    cluster: int | None = None

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
                # Group tokens into lines if they are close enough and in the same cluster
                if (abs(line[0].bbox.y0 - word.bbox.y0) < self.epsilon and
                    word.cluster == line[0].cluster):
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
                # Group tokens into columns if they are close enough and in the same cluster
                if (abs(column[0].bbox.x0 - word.bbox.x0) < self.epsilon and
                    word.cluster == column[0].cluster):
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


    @classmethod
    def from_dbscan(cls, words: list[Word], epsilon: float = 5) -> "Page":
        return cls(words=words, epsilon=epsilon)



class Document(BaseModel):
    pages: list[Page]


    def __str__(self) -> str:
        return "\nNEW PAGE\n".join([str(page) for page in self.pages])
    

    def as_columns(self) -> str:
        return "\nNEW PAGE\n".join([str(page.as_columns()) for page in self.pages])


    @classmethod
    def from_dbscan(cls, words: list[Word], epsilon: float = 5) -> "Document":
        coords = [w.bbox.center() for w in words]
        clusters = DBSCAN(eps=25, min_samples=2).fit(coords)

        # Print the number of clusters
        print(f"Number of clusters: {len(set(clusters.labels_)) - (1 if -1 in clusters.labels_ else 0)}")
        print(f"Number of words: {len(words)}")

        for word, cluster in zip(words, clusters.labels_):
            word.cluster = cluster

        # Create visualization
        plt.figure(figsize=(12, 8))
        colors = plt.cm.Set3(np.linspace(0, 1, len(set(clusters.labels_))))

        for word in words:
            x, y = word.bbox.center()
            cluster_id = word.cluster if word.cluster >= 0 else -1
            color = colors[cluster_id] if cluster_id >= 0 else 'black'
            plt.scatter(x, -y, c=[color], alpha=0.6, s=50)
            plt.text(x, -y, word.text, fontsize=6, ha='center', va='center')

        plt.title("DBSCAN Clusters")
        plt.xlabel("X coordinate")
        plt.ylabel("Y coordinate (inverted)")
        plt.savefig('clusters.png', dpi=150, bbox_inches='tight')
        plt.close()
        print("Cluster visualization saved as 'clusters.png'")

        pages = []
        pages.append(Page.from_dbscan(words=words, epsilon=epsilon))

        return cls(pages=pages)



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

    document = Document.from_dbscan(words=words, epsilon=5)

#    print(document.as_columns())



if __name__ == "__main__":
    main()
