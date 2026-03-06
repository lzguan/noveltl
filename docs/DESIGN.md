# Design document

**Last Updated**: December 2025  
**Status**: Outdated

> ⚠️ **DEPRECATION NOTICE**: This document has been superseded by the following focused documentation:
> - [architecture.md](architecture.md) - System architecture and microservices
> - [database-schema.md](database-schema.md) - Database schema and design rationale
> - [permissions.md](permissions.md) - Access control and permission system
> - [background-jobs.md](background-jobs.md) - AutoLabel worker system
> 
> This file is kept for historical reference. For current design information, please refer to the above documents.

---

The goal with this project is to create a platform for a trusted group of users to assist in translations. Specifically, we aim to create tooling to assist in the following tasks:
- Store and organize documents to be translated.
- Provide a framework to be able to use Named Entity Recognition (NER) models to label data from documents automatically.
- Provide a platform for users to be able to manually add/edit labels (including those generated from the NER model).
- View statistics/aggregate data about labels for specific documents/document classes.
- Use data about the labels to feed into some sort of translation software (for example, an LLM) to ensure consistent translations.

In this document, we will outline the specifications for this project and describe the models/decisions used to achieve this.

### Motivation

Right now, Large Language Models (LLMs) are an effective tool for creating high-quality translations for short documents. For longer documents, especially novels, LLMs have issues translating names consistently. To solve this problem, a tool to be able to identify all named entities in a novel is essential. The overall goal for this project is to present a platform for users to be able to efficiently automatically label data, while providing room to edit labeling, and for users to be able to use this labeling in LLM translations along with the capacity to edit these translations. At the moment, this project is tailored specifically to novel translations, which explains some of the naming decisions. 

### High level overview

We will divide this applications into distinct services. 

#### Users
- This service will handle user authentication, along with storing user metadata. 
- Other services will retrieve information about the current user from this service to determine user read/write permissions for that specific service.
- There are two types of users: _admin_ and _user_. Admins have near full access to modify anything in the database, while users have restricted functionality.
#### Novels
- This service will store metadata about novels, along with the actual text for chapters. 
- The service will store a database of _novels_, which in turn will be associated with a list of _raw chapters_.
- In order to ensure that editing chapters does not affect labeling, we associate each chapter with a list of _raw chapter revisions_. Revisions can be marked as final to mark them as immutable. 
- (Removed 12/22/2025) ~~Both users and guests are able to access all novels and chapters. Chapter revisions can be marked as either public or private. Chapter revisions marked as private can only be accessed to admins, while chapter revisions marked as public can be accessed by all users.~~
- (Update 12/22/2025) Permissions update
    - We assign each novel a _visibility level_, which will determine which users can see it and through what requests. Specifically, there are 3 types of requests we need to distinguish between: 
        1. **Search/filter queries**, where a user searches for a novel by name/some properties
        2. **ID queries**, where a user queries a novel based on its unique id
        3. **On create**, where a user wishes to create a novel but may potentially create a novel with a duplicate name/source content as another novel. This point is especially important for the webnovel space as source material will almost not be from this application.
    - We will fine grain permissions based on these three request types. Our four permission types will be as follows:
        1. **Private** - only the owner of the novel and corresponding contributors can see this novel through any request.
        2. **Restricted** - when a request to create a novel has some property that matches an 'alias' (a term that will be defined later, TBD) for this novel, the user creating the novel will have an option to send an anonymous request to all owners working on a matching novel. Otherwise this category has the same visibility as private.
        3. **Unlisted** - any user can query the id of this novel and be able to view it. However, the novel will not show up in search queries.
        4. **Public** - this novel is accessible to requests.
    - Each novel will have a list of contributors, along with an owner. These will be stored in an associative array with entries of the form (user, novel, contributor_type).
    - Each chapter revision will be either public or not public. Public chapter revisions will be visible to all user requests so long as the user has the permissions to view the novel. Otherwise, only contributors to the novel will have permissions to view the chapter.
    - To account for translations, novels will be able to link to other novels via nullable _novel parent_ foreign keys. Novels can then be classified into _novel types_ - for example, `'translation'`, `'original'`, etc.

#### Labels
- This service will store information about the labeling for novels. 
- Labels are associated with _label groups_, which can be further subdivided into _label datas_, each associated with a single chapter revision (not just chapter). Specific _labels_ are then associated to Label Datas. 
- Each label consists of a start/end position, along with the word being labeled and a text category (e.g. PERSON, LOCATION, etc.).
- (Removed 12/25/2025) ~~Each label group is associated with a novel and a user. The only users able to access this label group now are the user that created this label group and the admins.~~
- (Update 12/25/2025) We handle contributors in the same way as with novels for this service. Will write more details later. One difference between labels and novels is that labels should have an option to be _publically editable_ in addition to the _public_ option. We will also add the constraint that a label group must be public in order for it to be publically editable.

### Auto Labels
- Users are able to call an autolabeler on a list of raw chapter revisions that they have access to. The results of these calls will be stored as _auto labels_, for which each one is associated with a chapter revision, along with a _model_ and the parameters used in that model. Users can then pull results in auto labels to be used in label groups. Auto labels store the auto-labeled data in JSON format.
    - The reason we store the results of autolabeling into auto labels is to limit NER calls. Two users may be working on the same novel and may wish to both autogenerate labels using the same model. 
- When a user tries to invoke an autolabel request, they may face some delays due to the computation-intensive nature of autolabeling. This is especially true for batch requests: a user may request to label an entire novels' worth of chapters at once. To solve this issue, we offload requests to be done in increments and allow the user to see the status of any request. Unless explicitly specified by the user, they should not be allowed to update already completed autolabels. The user should always be allowed to re-request updates regardless of whether they get processed or not, and should be informed of the status of their request after they send it.
- Implementation details:
    - Each auto label in the database can have 4 states: `FAILED`, `PENDING`, `PROCESSING`, and `DONE`. 
    - When a user wishes to autolabel a raw chapter revision, the server will create an autolabel in database if it doesn't exist yet and move the request to a redis queue to be sent to a processing server running a worker. The server will then mark the autolabel status as `PENDING` in the database and update the `auto_label_last_job_request_id` to some new job request. This step will only occur when one of the following conditions is true:
        - If the autolabel did not yet exist in the server
        - If the autolabel status is marked as `FAILED`
        - If the autolabel status is otherwise not marked as `DONE` and the last request to autogenerate this autolabel occured some time ago (rate limiting)
    - A worker server will pick up requests from the redis queue and process them according to the following protocol:
        - When the worker server first picks up a job request, it tries to update the corresponding autolabel in db (with matching `auto_label_id` and `job_id`) to `PROCESSING` status. If nothing gets updated (i.e. the `job_id` the worker receives does not match), then the worker returns without performing any action.
        - The worker will then try to run inference in another thread. If this process fails/returns an exception, the worker will write `FAILED` to the database, under the condition that the `job_id` that the current thread has matches the one in the database.
        - If inference succeeds, the worker will write the results of inference to the database, under the condition that the `job_id` still matches. 

- Users are able to aggregate data in a label group to create _glossaries_. Each glossary corresponds to a label group. A glossary stores a JSON dict with entries of the form `term : (translation_of_term, description_of_term)`. Users must manually regenerate glossaries to ensure they are up to date with the current labelling. Glossaries that are not up to date with labelling are marked as such.

