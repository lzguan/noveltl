# Documentation for text/label editor

**Last updated:** 2026-06-02

This directory contains the documentation for the text/label editor. Since this is a fairly complex piece of code, we will organize the documentation into several chapters. 

This documentation will primarily be conceptual rather than going deep into implementation details. We aim to give the reader a mental model for the editor.

## Requirements

See [labels.md](../labels.md) and [novels.md](../novels.md) for database model. See [filters.md](../filters.md) and [autolabels.md](../autolabels.md) for information about other services.

The goal for this editor is to give the user a real-time way to edit the text/labels of a chapter on the frontend, as well as to display it in a viewer-friendly format. Specifically, the user needs to be able to perform the following operations:

- Insert text by typing/copy-pasting/composition events
- Remove text by pressing backspace/deleting highlighted text
- Insert a label from a specific label group with the following workflow:
    - Highlight a section of the text
    - A popup appears in the style of a context menu that has a form the user can fill out to insert a label
    - User fills out form and label gets added to corresponding label group/rejected if invalid
- Modify bounds of label by dragging endpoints/drag-and-dropping entire label
- Add new label groups
- Navigate between chapters
- Perform bulk operations such as filtering/autolabeling/etc.
- Display overlapping labels from multiple label groups
- Display a list of all label groups for a given novel
- Autosave (unsurprisingly, this is the most difficult requirement to implement)

Since highlighting is a somewhat ambiguous operation (is the user's intention to label or to delete text?), we will add a mode toggler between viewing mode, labeling mode, and editing mode. Users will only be able to perform relevant operations of the corresponding type when in any mode.

The text/label editor does not need to provide functionality between simultaneous editing between several users. It should however keep a consistent data model on the backend.

## List of chapters

1. Backend - [backend.md](./backend.md)
2. Controller - [controller.md](./controller.md)
3. Rendering - [rendering.md](./rendering.md)