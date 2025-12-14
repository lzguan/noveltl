# Monkeypatching

Last updated: 2025-12-13

This document is intended to summarize the author's experience with learning monkeypatching, as well as their experience with using it for testing in this project.

There will be various code snippets in this doc, along with links to files in the `tests/demos/monkeypatching` directory. The user is invited to follow along according to the instructions posted at various intervals in this document.

All code here is tested in python 3.12

## &sect;1 - Motivation

One functionality that we wish to add for this project is the ability for a user to call an api to automatically label a list of raw chapter revisions. This is a slow, blocking task and hence it is important that we have the ability to offload this capability to run in the background. Furthermore, due to the ML nature of autolabeling, it would be significantly faster for the autolabeling to be done on a machine specialized for processing ML tasks. 

To solve this issue, we divide the backend into several different processes: 

1. A backend server responsible for processing user requests
2. A Postgres database that records all data (namely, data about autolabels)
3. A redis queue that receives compute-intensive/blocking tasks and transfers from the backend
4. A worker process that polls tasks from the redis queue, gathers the required information from the database, computes the result, and feeds it back into the database.

In the current `compose.yaml`, these processes are given by the services `backend`, `db`, `redis`, and `worker`, respectively. The reader is invited to look through the `Dockerfile` to see exactly what the build configuration is like. Note that these processes communicate via network connections and hence can be hosted on different machines.

The source code for the interaction between these services is fairly intricate in the case of autolabeling. When a user wishes to autolabel certain chapter revisions, they will call an API, which will in turn call `insert_auto_labels` in the `src.autolabels.service` module. When this function is called, a sequence of actions described in the design doc are executed. The reader may notice that the distributed nature of this sequence of instructions can cause many errors to pop up and as such, the error handling for each of these steps needs to be robust. Hence the `insert_auto_labels` function needs to be tested extensively.

It should be clear to the anyone that we do not want to test this function in the production environment. In this project, testing is done through another Postgres image called `test_db`. Connecting to `test_db` through the `insert_auto_labels` function is easy since `insert_auto_labels` takes a database connection (namely, an SQLAlchemy `Session`) as a parameter. 

On the other hand, the worker process is designed to run in isolation in another container and its task `autolabel_infer` (found in the `src.autolabels.worker.tasks` module) must only take parameters that correspond to information that the backend server can send it through the `redis` queue. This means that the worker should manage its own connection to the database, which is done through the `src.autolabels.worker.config` module. In the testing environment, we need a worker process that connects to a different `redis` queue (this can be done by creating a `redis` connection with the optional parameter `database` set to `1`), as well as connect to `test_db` instead of `db`. This is the problem that this document aims to describe a solution to. 

## &sect;2 - Python namespaces

`monkeypatch` is a `pytest` feature designed to override module imports. As such, it is important to understand how imports behave under the hood in python before we talk about `monkeypatch` specifically.

### &sect;2.1 - A couple of interesting examples
Demo files: `tests/demos/monkeypatching/basic_examples`

In python, there are several ways to use the `import` directive.
- `import module`
- `import module as alias`
- `from module import obj`.

Once any of these has been used, the modules (or the respective objects within the module) are accessible from the scope the `import` directive was called from. For example, consider the following Python module:
```python
# module.py
def f():
    print("f")
    g()

def g():
    print("g")
    def gg():
        print("gg")
    gg()

class H:
    def h(self):
        print("h")
        f()

x = H()
```
We can see how each of the three import methods will behave in the python shell. Try running each of these three blocks of code in separate python shells:

```python
>>> import module
>>> module.f()
f
g
gg
>>> module.g()
g
gg
>>> module.H().h()
<module.H object at 0x713a56949c70>
h
f
g
gg
>>> module.x()
<module.H object at 0x713a5694b2f0>
h
f
g
gg
```
```python
>>> import module as m
>>> m.x.h()
<module.H object at 0x77d5548ca9c0>
h
f
g
gg
```
```python
>>> from module import x
>>> x.h()
<module.H object at 0x77d5548ca9c0>
h
f
g
gg
```
The reader should already be familiar with the behaviour we have introduced so far. There are a couple of curious things that can occur if we try to import parts from the same model though: consider the following examples.

---
**Example 1**

Consider the following python program:
```python
# prog_1.py
import module
# m.x.h()
import module as m
```
When we uncomment line 2 in `prog_1.py`, this program will crash.
```console
$ python prog_1.py
Traceback (most recent call last):
  File "/workspaces/NovelTL_Dev/tests/demos/monkeypatching/namespace_basics/./prog_1.py", line 2, in <module>
    m.x.h()
    ^
NameError: name 'm' is not defined
```
However, if we swap line 2 and line 3, the program should work as expected.

---
**Example 2**
```python
>>> import module
>>> import module as m
```
Try running this in a new python shell. You should notice that nothing crashes at this point. But how do we access objects in `module`? Do we use `m.(...)` or `module.(...)`? Try running the following commands in the python shell and see how they behave:
```python
>>> module.x.h()
>>> m.x.h()
```
You should notice that both these commands will successfully execute. Furthermore, the addresses of the `x` objects should be the same:
```python
>>> m.x
<module.H object at 0x77d5548ca9c0>
>>> module.x
<module.H object at 0x77d5548ca9c0>
```
If we use the `from` keyword, we will see that the address of `x` imported using the `from` keyword remains the same.
```python
>>> from module import x
>>> x
<module.H object at 0x77d5548ca9c0>
```
---
**Example 3**

Consider what happens when we import `module` inside a function: in a new shell, define the following function.
```python
>>> def q():
        import module
        module.x.h()
```
Calling an object in module should fail at this point.
```python
>>> module.f()
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
NameError: name 'module' is not defined
```
This is because we have not yet run the `import module` command. A more interesting question would be whether we are able to run `module.f()` after we have run `q()`. Try running the following commands:
```python
>>> q()
>>> module.f()
```
What happens here? The reader should notice that the call `q()` succeeds and runs `module.x.h()`. However, the call `module.f()` will fail:
```
 Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
NameError: name 'module' is not defined
```
---

Let's summarize what we have learned from these three examples.

1. Python keeps track of all module imports dynamically. The list of modules that we can use changes depending on where we are in the program.
2. Python caches all module imports and redirects imports from the same module under a different name to the underlying cached object.
3. Python scopes module imports so that an import in a specific scope cannot be accessed by a larger scope.

How does python enforce this behaviour?

### &sect;2.2 - Namespaces and scopes
Demo files: `tests/demos/monkeypatching/namespaces

For every dynamic object there is an associated in-memory data structure. In this case, python dynamically keeps track of all available-to-use names in dictionaries called _namespaces_. Let us make these definitions clear:

**Definition 1**

A namespace is a dictionary mapping of names to Python objects. Every object resides in a namespace, and can be accessed by querying the corresponding name in the namespace.

**Definition 2**

The scope of a namespace is the region of code in which that namespace can be accessed.

Surprisingly, we can actually access these namespaces in python! We will list some of the different namespaces and the underlying objects they are associated with.

- Each module has its own namespace. The corresponding namespaces can be accessed via the `module.__dict__` attribute.
- There is a global namespace that can be accessed via `globals()`.
- Each 

Let's see some examples. 

Test addition