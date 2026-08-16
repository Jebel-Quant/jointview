import marimo

__generated_with = "0.23.15"
app = marimo.App(width="full")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    from jointview.data import load_frame
    from jointview.plot import default_pair, joint_chart, joint_frame

    # marimo run app.py -- --data prices.parquet
    frame = load_frame(mo.cli_args().get("data"))
    columns = frame.columns
    return columns, default_pair, frame, joint_chart, joint_frame


@app.cell
def _(default_pair, frame, mo):
    x_start, y_start = default_pair(frame)
    get_x, set_x = mo.state(x_start)
    get_y, set_y = mo.state(y_start)
    return get_x, get_y, set_x, set_y


@app.cell
def _(columns, mo, set_x, set_y):
    # The steppers live in their own cell: they must not read the state they write,
    # or marimo would rebuild them on every click and lose the button identity.
    def _step(setter, delta):
        return lambda _: setter(lambda i: (i + delta) % len(columns))

    x_back = mo.ui.button(label="◀", on_change=_step(set_x, -1))
    x_next = mo.ui.button(label="▶", on_change=_step(set_x, +1))
    y_back = mo.ui.button(label="◀", on_change=_step(set_y, -1))
    y_next = mo.ui.button(label="▶", on_change=_step(set_y, +1))
    return x_back, x_next, y_back, y_next


@app.cell
def _(columns, get_x, get_y, mo, set_x, set_y):
    # Reads the state and writes it back on click. marimo does not re-run the cell
    # that called a setter, so this is a two-way binding rather than a loop.
    x_pick = mo.ui.radio(
        options=columns,
        value=columns[get_x()],
        on_change=lambda name: set_x(columns.index(name)),
    )
    y_pick = mo.ui.radio(
        options=columns,
        value=columns[get_y()],
        on_change=lambda name: set_y(columns.index(name)),
    )
    return x_pick, y_pick


@app.cell
def _(columns, frame, get_x, get_y, joint_chart, joint_frame):
    x_column = columns[get_x()]
    y_column = columns[get_y()]
    chart = joint_chart(frame, x_column, y_column)
    drawn = joint_frame(frame, x_column, y_column).height
    return chart, drawn, x_column, y_column


@app.cell
def _(mo):
    def panel(title, back, next_, picker):
        return mo.vstack(
            [
                mo.md(f"**{title}**"),
                mo.hstack([back, next_], justify="start", gap=0.25),
                mo.vstack([picker]).style(
                    {"max-height": "62vh", "overflow-y": "auto", "padding-right": "0.5rem"}
                ),
            ],
            gap=0.5,
        )

    return (panel,)


@app.cell
def _(chart, drawn, frame, mo, x_column, y_column):
    _dropped = frame.height - drawn
    _note = f" of {frame.height:,}" if _dropped else ""
    caption = mo.md(
        f"`{x_column}` × `{y_column}` — {drawn:,}{_note} rows plotted. "
        "Drag a box on the scatter to highlight that slice in both marginals."
    )
    figure = mo.vstack([chart, caption], gap=0.5, align="center")
    return (figure,)


@app.cell
def _(figure, mo, panel, x_back, x_next, x_pick, y_back, y_next, y_pick):
    mo.hstack(
        [
            panel("x-axis", x_back, x_next, x_pick),
            figure,
            panel("y-axis", y_back, y_next, y_pick),
        ],
        widths=[1, 6, 1],
        align="start",
        gap=1.5,
    )
    return


if __name__ == "__main__":
    app.run()
