# Naming conventions

## General
- Class names should be `PascalCase`.
- Functions, class attributes and methods should be `snake_case`.

## Database Models
- Names of columns should be `snake_case`.
- Table names should describe the thing stored in each row as plural (e.g. `fruits`, `houses`, etc.).
- Properties of `x` (columns in table `xs`) should be called `x_field_name` (e.g. `Fruit.fruit_name` in table named `fruits`).
- If `x` has a ForeignKey to `y`, the corresponding relationships should be defined by `y_of_x` in `x` and `xs_of_y` in `y` (e.g. `fruits_with_colour` in table `colours` and `colour_of_fruit` in table `fruits`).
- If `x` has a ForeignKey to `y`, the ForeignKey column name should be called `y_id` in `x` e.g. `colour_id` in table `fruits`.
- Convention may be broken in the case that breaking a naming convention gives a more descriptive column.

## Pydantic Schemas
- Objects intended for return to users should be self-describing.
- If such an object is associated with a db model, then the object should share the name with the db model, possibly with some suffix attached.
- _Example_:
    ```python
        # db model
        class LabelData(Base):
            some_metadata
            some_large_data
    ```
    ```python
        # pydantic schema
        class LabelData(BaseModel):
            some_metadata
            some_large_data
        
        class LabelDataMeta(BaseModel):
            some_metadata
    ```
- Pydantic models associated with specific user requests should be of the form `VerbObject` related to what the user wishes to do (e.g. `CreateObject`, `DeleteObject`, `UpdateObject`).
- If a module needs to send an ACK to client, should define a `OperationStatus` pydantic schema, where Operation is the operation that needs to be ACKed. 

## Service Modules:
- Names of service functions should follow the rules below: 
    - `query_object` for database queries
    - `modify_object` for database updates
    - `insert_object` for database inserts
    - `remove_object` for database removes
    - `action_object` for more specific actions
    - Optionally, add a `with_restriction` suffix to above names when need to restrict queries to certain objects
    - Optionally, add a `by_method` suffix to above names when method of performing operation is specified (e.g. `modify_label_data_by_stream` vs. `modify_label_data`).
    - For aggregate data, make the object in question plural.
- Parameters should go in the order of
    1. db
    2. other dependencies
    3. primitive data types corresponding to path variables
    4. other data
    5. form data (e.g. pydantic models)
- There should be no keyword arguments here.
- Try to be consistent with parameter order.
- Any dependency that the router layer has should be passed to this layer.

## Router Modules
- Names of functions should follow the rules below:
    - `read_object` for GET requests
    - `create_object` for POST requests
    - `update_object` for PATCH requests
    - `delete_object` for DELETE requests
    - For more specific verbs, append one of the four verbs above to denote the specific category (e.g. `update_publish_chapter_revision`).
    - Use plural for functions corresponding to endpoints that operate on a collection.
    - Use singular for functions corresponding to endpoints that operate on a single item.
- Parameters should go in the order of
    1. Path parameters
    2. Required query parameters (if applicable)
    3. Request body (if applicable)
    4. Dependencies (e.g. `param : Annotated[Type, Depends(dependency_fn)]`)
    5. Optional query parameters
- Try to be consistent with parameter order.
- Any dependencies that a router needs should be passed to the service layer.

## Router endpoints
- As a general guideline, try to follow RESTful API naming conventions.
- Separating words should be done with spaces.
- Use lowercase letters.
- Retrieving objects specified by id should be done through the endpoint `GET objects/{object_id}`.
- Inserting an object owned by another object should be done through the endpoint `POST owning-objects/{owning_object_id}/objects` (e.g. `novels/{novel_id}/raw_chapters`).
- Inserting an object not owned by any other object should be done through the endpoint `POST /objects` (e.g. `POST /novels`).
- Updating an object with specified id should be done through the endpoint `PATCH /objects/{object_id}`.
- Deleting an object with specified id should be done through the endpoint `DELETE /objects/{object_id}`.
- Bulk querying an object by some filters should be done throug the endpoint `GET /objects` (e.g. `GET /raw-chapter-revisions`).
- Use your own judgement for anything else. We will keep updating this part.

# Exceptions
- Be descriptive.
- Use common sense.
- TODO: make actual rules for this section.

# Exception handling
- Custom exceptions should be defined in `exceptions.py` in each feature directory (e.g. `src/auth/exeptions.py`)
- Custom/pythonic exceptions should be raised in service modules on error, as opposed to returning error codes. Possible raised exceptions must be clearly outlined in docstring.
- Router functions are responsible for handling custom exceptions raised from service modules.
- If an exception is raised, no more db calls should be made to preserve atomicity.