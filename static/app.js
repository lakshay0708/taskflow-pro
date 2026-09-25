"use strict";

var API_BASE = "/api";
var COLUMN_ORDER = ["Backlog", "In Progress", "Review", "Done"];

var board = {
    columns: COLUMN_ORDER,
    tasks: [],
    dependencies: []
};

var pendingTaskId = null;
var pendingSuggestions = [];

async function request(path, options) {
    var settings = Object.assign(
        { headers: { "Content-Type": "application/json" } },
        options || {}
    );

    var response = await fetch(API_BASE + path, settings);
    var raw = await response.text();
    var data = null;

    if (raw) {
        try {
            data = JSON.parse(raw);
        } catch (err) {
            data = null;
        }
    }

    if (!response.ok) {
        var detail = data && data.detail
            ? data.detail
            : "Request failed: " + response.status;

        throw new Error(
            typeof detail === "string"
                ? detail
                : JSON.stringify(detail)
        );
    }

    return data;
}

function showMessage(text, isError) {
    var box = document.getElementById("message");

    box.textContent = text;
    box.className = isError ? "message error" : "message";
    box.hidden = false;

    if (!isError) {
        window.setTimeout(function () {
            box.hidden = true;
        }, 4000);
    }
}

async function loadBoard() {
    try {
        board = await request("/board", { method: "GET" });
        render();
    } catch (err) {
        showMessage(
            "Cannot reach the server. Check that uvicorn is still running. (" +
            err.message +
            ")",
            true
        );
    }
}

function taskById(id) {
    for (var i = 0; i < board.tasks.length; i++) {
        if (board.tasks[i].id === id) {
            return board.tasks[i];
        }
    }

    return null;
}

function prereqLinks(taskId) {
    return board.dependencies.filter(function (link) {
        return link.task_id === taskId;
    });
}

var MONTHS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
];

function prettyDate(iso) {
    if (!iso) {
        return "unscheduled";
    }

    var parts = iso.split("-");

    return Number(parts[2]) + " " + MONTHS[Number(parts[1]) - 1];
}

function todayIso() {
    var now = new Date();
    var month = String(now.getMonth() + 1);
    var day = String(now.getDate());

    if (month.length < 2) {
        month = "0" + month;
    }

    if (day.length < 2) {
        day = "0" + day;
    }

    return (
        now.getFullYear() +
        "-" +
        month +
        "-" +
        day
    );
}

function render() {
    var boardEl = document.getElementById("board");

    boardEl.textContent = "";

    COLUMN_ORDER.forEach(function (name) {
        boardEl.appendChild(buildColumn(name));
    });

    updateStatusLine();
    fillDependencyDropdowns();
}

function buildColumn(name) {
    var column = document.createElement("section");
    column.className = "column";
    column.dataset.column = name;

    var tasks = board.tasks.filter(function (task) {
        return task.status === name;
    });

    var head = document.createElement("div");
    head.className = "column-head";

    var heading = document.createElement("h2");
    heading.textContent = name;

    var count = document.createElement("span");
    count.className = "column-count";
    count.textContent = tasks.length;

    head.appendChild(heading);
    head.appendChild(count);
    column.appendChild(head);

    if (tasks.length === 0) {
        var empty = document.createElement("p");
        empty.className = "column-empty";
        empty.textContent =
            name === "Backlog"
                ? "Add a task to get started."
                : "Drag a card here.";

        column.appendChild(empty);
    }

    tasks.forEach(function (task) {
        column.appendChild(buildCard(task));
    });

    column.addEventListener("dragover", function (event) {
        event.preventDefault();
        column.classList.add("drag-over");
    });

    column.addEventListener("dragleave", function () {
        column.classList.remove("drag-over");
    });

    column.addEventListener("drop", function (event) {
        event.preventDefault();
        column.classList.remove("drag-over");

        var id = Number(
            event.dataTransfer.getData("text/plain")
        );

        if (id) {
            moveTask(id, name);
        }
    });

    return column;
}

function buildCard(task) {
    var card = document.createElement("article");
    var classes = ["card"];

    if (task.is_critical) {
        classes.push("critical");
    }

    if (task.is_blocked) {
        classes.push("blocked");
    }

    card.className = classes.join(" ");
    card.draggable = true;
    card.dataset.id = task.id;

    var title = document.createElement("p");
    title.className = "card-title";
    title.textContent = task.title;
    card.appendChild(title);

    var path = document.createElement("span");

    if (task.is_critical) {
        path.className = "path-tag";
        path.textContent = "Critical path";
    } else {
        path.className = "slack-tag";
        path.textContent =
            "Slack: " +
            task.slack_days +
            (task.slack_days === 1 ? " day" : " days");
    }

    card.appendChild(path);

    if (task.description) {
        var notes = document.createElement("p");
        notes.className = "card-notes";
        notes.textContent = task.description;
        card.appendChild(notes);
    }

    if (task.is_blocked) {
        var badge = document.createElement("span");
        badge.className = "badge";
        badge.textContent =
            "Blocked: a prerequisite is unfinished";
        card.appendChild(badge);
    }

    var dates = document.createElement("p");
    dates.className = "card-dates";

    var dateText = document.createElement("span");
    dateText.textContent =
        prettyDate(task.start_date) +
        " to " +
        prettyDate(task.end_date) +
        " (" +
        task.duration_days +
        (task.duration_days === 1 ? " day) " : " days) ");

    dates.appendChild(dateText);

    var shorter = document.createElement("button");
    shorter.type = "button";
    shorter.className = "nudge";
    shorter.textContent = "-1 day";
    shorter.disabled = task.duration_days <= 1;

    shorter.addEventListener("click", function () {
        changeDuration(
            task.id,
            task.duration_days - 1
        );
    });

    var longer = document.createElement("button");
    longer.type = "button";
    longer.className = "nudge";
    longer.textContent = "+1 day";

    longer.addEventListener("click", function () {
        changeDuration(
            task.id,
            task.duration_days + 1
        );
    });

    dates.appendChild(shorter);
    dates.appendChild(longer);
    card.appendChild(dates);

    var links = prereqLinks(task.id);

    if (links.length > 0) {
        var box = document.createElement("div");
        box.className = "prereqs";
        box.appendChild(
            document.createTextNode("Waits for:")
        );

        links.forEach(function (link) {
            var upstream = taskById(link.depends_on_id);

            var chip = document.createElement("span");
            chip.className = "chip";

            chip.appendChild(
                document.createTextNode(
                    upstream
                        ? upstream.title
                        : "task " + link.depends_on_id
                )
            );

            var unlink = document.createElement("button");
            unlink.type = "button";
            unlink.textContent = "x";
            unlink.title = "Remove this dependency";

            unlink.addEventListener("click", function () {
                removeDependency(link.id);
            });

            chip.appendChild(unlink);
            box.appendChild(chip);
        });

        card.appendChild(box);
    }

    var actions = document.createElement("div");
    actions.className = "card-actions";

    var here = COLUMN_ORDER.indexOf(task.status);

    var back = document.createElement("button");
    back.type = "button";
    back.textContent = "Back";
    back.disabled = here <= 0;

    back.addEventListener("click", function () {
        moveTask(
            task.id,
            COLUMN_ORDER[here - 1]
        );
    });

    var forward = document.createElement("button");
    forward.type = "button";
    forward.textContent = "Forward";

    forward.disabled =
        here < 0 ||
        here >= COLUMN_ORDER.length - 1 ||
        task.is_blocked === 1;

    forward.addEventListener("click", function () {
        moveTask(
            task.id,
            COLUMN_ORDER[here + 1]
        );
    });

    var remove = document.createElement("button");
    remove.type = "button";
    remove.className = "remove";
    remove.textContent = "Delete";

    remove.addEventListener("click", function () {
        deleteTask(task.id, task.title);
    });

    actions.appendChild(back);
    actions.appendChild(forward);
    actions.appendChild(remove);

    card.appendChild(actions);

    card.addEventListener("dragstart", function (event) {
        event.dataTransfer.setData(
            "text/plain",
            String(task.id)
        );

        event.dataTransfer.effectAllowed = "move";
        card.classList.add("dragging");
    });

    card.addEventListener("dragend", function () {
        card.classList.remove("dragging");
    });

    return card;
}

function updateStatusLine() {
    var total = board.tasks.length;

    var blocked = board.tasks.filter(function (task) {
        return task.is_blocked === 1;
    }).length;

    var done = board.tasks.filter(function (task) {
        return task.status === "Done";
    }).length;

    var critical = board.tasks.filter(function (task) {
        return task.is_critical === 1;
    }).length;

    var text;

    if (total === 0) {
        text =
            "No tasks yet. Add one on the left, or run " +
            "python seed.py for the demo project.";
    } else {
        text =
            total +
            " tasks, " +
            done +
            " finished, " +
            blocked +
            " waiting on unfinished work, " +
            critical +
            " on the critical path.";
    }

    document.getElementById("status-line").textContent = text;
}

function fillDependencyDropdowns() {
    [
        document.getElementById("dep-task"),
        document.getElementById("dep-prereq")
    ].forEach(function (select) {
        var previous = select.value;

        select.textContent = "";

        board.tasks.forEach(function (task) {
            var option = document.createElement("option");

            option.value = task.id;
            option.textContent = task.title;

            select.appendChild(option);
        });

        if (previous) {
            select.value = previous;
        }
    });
}

async function moveTask(taskId, status) {
    if (!status) {
        return;
    }

    try {
        var result = await request(
            "/tasks/" + taskId + "/status",
            {
                method: "PATCH",
                body: JSON.stringify({
                    status: status
                })
            }
        );

        board = result.board;
        render();
    } catch (err) {
        showMessage(err.message, true);
    }
}

async function changeDuration(taskId, days) {
    if (days < 1) {
        return;
    }

    try {
        var result = await request(
            "/tasks/" + taskId + "/duration",
            {
                method: "PATCH",
                body: JSON.stringify({
                    duration_days: days
                })
            }
        );

        board = result.board;
        render();
    } catch (err) {
        showMessage(err.message, true);
    }
}

async function deleteTask(taskId, title) {
    if (
        !window.confirm(
            'Delete "' +
            title +
            '" and every link to it?'
        )
    ) {
        return;
    }

    try {
        var result = await request(
            "/tasks/" + taskId,
            {
                method: "DELETE"
            }
        );

        board = result.board;
        render();

        showMessage(
            'Deleted "' + title + '".',
            false
        );
    } catch (err) {
        showMessage(err.message, true);
    }
}

async function addDependency(taskId, prereqId) {
    try {
        var result = await request(
            "/dependencies",
            {
                method: "POST",
                body: JSON.stringify({
                    task_id: taskId,
                    depends_on_id: prereqId
                })
            }
        );

        board = result.board;
        render();

        showMessage("Linked.", false);
        return true;
    } catch (err) {
        showMessage(err.message, true);
        return false;
    }
}

async function removeDependency(dependencyId) {
    try {
        var result = await request(
            "/dependencies/" + dependencyId,
            {
                method: "DELETE"
            }
        );

        board = result.board;
        render();
    } catch (err) {
        showMessage(err.message, true);
    }
}

async function createTask() {
    var titleInput =
        document.getElementById("task-title");

    var title = titleInput.value.trim();

    if (!title) {
        showMessage(
            "Give the task a title before adding it.",
            true
        );

        titleInput.focus();
        return;
    }

    var payload = {
        title: title,
        description:
            document
                .getElementById("task-description")
                .value
                .trim(),
        duration_days:
            Number(
                document.getElementById("task-days").value
            ) || 1,
        planned_start:
            document.getElementById("task-start").value ||
            null
    };

    try {
        var result = await request(
            "/tasks",
            {
                method: "POST",
                body: JSON.stringify(payload)
            }
        );

        board = result.board;
        render();

        titleInput.value = "";
        document.getElementById(
            "task-description"
        ).value = "";

        showMessage(
            'Added "' + title + '".',
            false
        );

        await offerSuggestions(
            result.created_id,
            title
        );
    } catch (err) {
        showMessage(err.message, true);
    }
}

async function offerSuggestions(taskId, title) {
    var result = null;

    try {
        result = await request(
            "/suggestions",
            {
                method: "POST",
                body: JSON.stringify({
                    task_id: taskId
                })
            }
        );
    } catch (err) {
        console.log(
            "Suggestions unavailable:",
            err.message
        );
        return;
    }

    if (
        !result ||
        !result.suggestions ||
        result.suggestions.length === 0
    ) {
        return;
    }

    pendingTaskId = taskId;
    pendingSuggestions = result.suggestions;

    var intro =
        result.source === "llm"
            ? 'An AI model read your existing task list and thinks "' +
              title +
              '" may need these finished first. Nothing is added until you approve it.'
            : "The AI model was unavailable, so these come from keyword matching against your existing tasks. Nothing is added until you approve it.";

    document.getElementById(
        "suggest-intro"
    ).textContent = intro;

    var list =
        document.getElementById("suggest-list");

    list.textContent = "";

    pendingSuggestions.forEach(function (item, index) {
        var row = document.createElement("label");
        row.className = "suggestion";

        var tick = document.createElement("input");
        tick.type = "checkbox";
        tick.checked = false;
        tick.dataset.index = index;

        var text = document.createElement("span");

        var name = document.createElement("div");
        name.className = "suggestion-title";
        name.textContent = item.title;

        var why = document.createElement("div");
        why.className = "suggestion-reason";
        why.textContent = item.reason || "";

        text.appendChild(name);
        text.appendChild(why);

        row.appendChild(tick);
        row.appendChild(text);
        list.appendChild(row);
    });

    document.getElementById(
        "suggest-backdrop"
    ).hidden = false;
}

function closeSuggestDialog() {
    document.getElementById(
        "suggest-backdrop"
    ).hidden = true;

    pendingTaskId = null;
    pendingSuggestions = [];
}

async function acceptSuggestions() {
    var ticks = document.querySelectorAll(
        "#suggest-list input[type=checkbox]"
    );

    var chosen = [];

    ticks.forEach(function (tick) {
        if (tick.checked) {
            chosen.push(
                pendingSuggestions[
                    Number(tick.dataset.index)
                ]
            );
        }
    });

    var taskId = pendingTaskId;

    closeSuggestDialog();

    if (chosen.length === 0) {
        return;
    }

    var added = 0;

    for (var i = 0; i < chosen.length; i++) {
        var ok = await addDependency(
            taskId,
            chosen[i].id
        );

        if (ok) {
            added += 1;
        }
    }

    if (added > 0) {
        showMessage(
            "Approved " +
            added +
            " prerequisite" +
            (added === 1 ? "" : "s") +
            ".",
            false
        );
    }
}

document
    .getElementById("create-task")
    .addEventListener("click", createTask);

document
    .getElementById("task-title")
    .addEventListener("keydown", function (event) {
        if (event.key === "Enter") {
            createTask();
        }
    });

document
    .getElementById("create-dep")
    .addEventListener("click", function () {
        var taskId = Number(
            document.getElementById("dep-task").value
        );

        var prereqId = Number(
            document.getElementById("dep-prereq").value
        );

        if (!taskId || !prereqId) {
            showMessage(
                "Pick two tasks first.",
                true
            );
            return;
        }

        addDependency(taskId, prereqId);
    });

document
    .getElementById("suggest-skip")
    .addEventListener("click", closeSuggestDialog);

document
    .getElementById("suggest-accept")
    .addEventListener("click", acceptSuggestions);

document.getElementById("task-start").value = todayIso();

loadBoard();