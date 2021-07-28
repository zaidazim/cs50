from cs50 import get_string

text = get_string("Text: ")

## Variables to store count for letters, words and sentences
words = 1
letters = sentences = 0

for char in text:

    ## Count the number of letters
    if char.isalpha():
        letters += 1

    ## Count the number of words
    if char.isspace():
        words += 1

    ## Count the number of sentences
    if char in ['.', '!', '?']:
        sentences += 1


L =  (letters / words) * 100.0
S = (sentences / words) * 100.0

index = 0.0588 * L - 0.296 * S - 15.8
grade = round(index)

if grade >= 16:
    print("Grade 16+")
elif grade < 1:
    print("Before Grade 1")
else:
    print(f"Grade {grade}")





