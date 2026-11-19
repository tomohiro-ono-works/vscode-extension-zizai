define(["@jupyter-widgets/controls"], function (controls) {
    const choices = [
        ["header_row", "ヘッダー行に設定"],
        ["data_start_row", "データ開始行に設定"]
    ];

    class RowContextView extends controls.ButtonView {
        menuChoices() {
            return choices;
        }

        selectRole(role) {
            this.send({ event: "row-role", role });
        }

        render() {
            super.render();
            this.el.setAttribute("aria-haspopup", "menu");
            this.el.setAttribute("aria-expanded", "false");
            this.el.addEventListener("contextmenu", this);
            this.el.addEventListener("click", this);
            this.el.addEventListener("keydown", this);
        }

        handleEvent(event) {
            if (event.type === "contextmenu") {
                event.preventDefault();
                event.stopPropagation();
                this.openMenu(event.clientX, event.clientY);
            } else if (event.type === "click" || event.key === "ContextMenu"
                       || (event.shiftKey && event.key === "F10")) {
                event.preventDefault();
                const { left, bottom } = this.el.getBoundingClientRect();
                this.openMenu(left, bottom);
            }
        }

        openMenu(x, y) {
            if (this.model.get("disabled")) return;
            this.closeMenu();
            const menu = document.createElement("div");
            menu.className = "zizai-row-preview-menu";
            menu.setAttribute("role", "menu");
            menu.setAttribute("aria-label", this.model.get("description"));
            const items = this.menuChoices().map(([role, label]) => {
                const item = document.createElement("button");
                item.type = "button";
                item.setAttribute("role", "menuitem");
                item.textContent = label;
                item.onclick = () => {
                    this.selectRole(role);
                    this.closeMenu(true);
                };
                return item;
            });
            menu.append(...items);
            menu.onkeydown = event => {
                const index = items.indexOf(document.activeElement);
                if (event.key === "Escape" || event.key === "Tab") {
                    event.preventDefault();
                    event.stopPropagation();
                    this.closeMenu(true);
                } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
                    event.preventDefault();
                    items[(index + (event.key === "ArrowDown" ? 1 : items.length - 1)) % items.length].focus();
                }
            };
            const pane = this.el.closest(".row-preview");
            const viewport = document.documentElement;
            document.body.append(menu);
            const bounds = pane?.getBoundingClientRect();
            const top = Math.max(4, bounds?.top ?? 4);
            const bottom = Math.min(viewport.clientHeight, bounds?.bottom ?? viewport.clientHeight);
            // The notebook can clip the output below the row even when the widget iframe has room.
            const above = y - menu.offsetHeight - 4;
            const menuY = above >= top ? above : y;
            menu.style.left = `${Math.max(4, Math.min(x, viewport.clientWidth - menu.offsetWidth - 4))}px`;
            menu.style.top = `${Math.max(top, Math.min(menuY, bottom - menu.offsetHeight - 4))}px`;
            this.menu = menu;
            this.keepMenuVisible(menu);
            this.el.setAttribute("aria-expanded", "true");
            this.menuListeners = new AbortController();
            const options = { capture: true, signal: this.menuListeners.signal };
            document.addEventListener("pointerdown", event => {
                if (!menu.contains(event.target)) this.closeMenu();
            }, options);
            document.addEventListener("scroll", () => this.closeMenu(), options);
            window.addEventListener("resize", () => this.closeMenu(), options);
            items[0].focus({ preventScroll: true });
        }

        keepMenuVisible(menu) {
            // VS Code can clip the notebook output outside this iframe's own viewport.
            const observer = new IntersectionObserver(([entry]) => {
                observer.disconnect();
                if (this.menu !== menu || entry.intersectionRect.height === 0) return;
                const box = entry.boundingClientRect;
                const visible = entry.intersectionRect;
                const clippedTop = visible.top - box.top;
                const clippedBottom = box.bottom - visible.bottom;
                if (clippedTop > 1 || clippedBottom > 1) {
                    menu.style.top = `${Math.max(4, box.top + Math.ceil(clippedTop) - Math.ceil(clippedBottom))}px`;
                }
            });
            observer.observe(menu);
        }

        closeMenu(returnFocus = false) {
            this.menuListeners?.abort();
            this.menu?.remove();
            this.menu = null;
            this.el.setAttribute("aria-expanded", "false");
            if (returnFocus) this.el.focus({ preventScroll: true });
        }

        remove() {
            this.closeMenu();
            return super.remove();
        }
    }

    class ColumnContextView extends RowContextView {
        render() {
            super.render();
            this.el.draggable = !this.model.get("_pending_delete");
            for (const event of ["dblclick", "dragstart", "dragover", "dragleave", "drop", "dragend"]) {
                this.el.addEventListener(event, this);
            }
        }

        menuChoices() {
            return Object.entries(this.model.get("_menu_items"));
        }

        selectRole(role) {
            this.send({ event: "column-operation", role });
        }

        handleEvent(event) {
            const { type, key } = event;
            if (type === "dblclick" || (type === "keydown" && key === "F2")) {
                event.preventDefault();
                this.renameInPlace();
            } else if (type === "dragstart") {
                this.startDrag(event);
            } else if (type === "dragover") {
                this.markDropTarget(event);
            } else if (type === "drop") {
                this.dropColumn(event);
            } else if (type === "dragleave" || type === "dragend") {
                this.clearDropTarget();
            } else if (type !== "click") {
                super.handleEvent(event);
            }
        }

        renameInPlace() {
            if (this.renameInput || this.model.get("_pending_delete")) return;
            this.closeMenu();
            const header = this.el.getBoundingClientRect();
            const heading = this.el.parentElement;
            const input = document.createElement("input");
            input.type = "text";
            input.className = "zizai-column-rename";
            input.value = this.model.get("_column_name");
            input.setAttribute("aria-label", "新しい列名");
            input.style.setProperty("--column-editor-width", `${header.width}px`);
            input.style.left = `${header.left - heading.getBoundingClientRect().left}px`;
            this.renameInput = input;
            const finish = (confirm) => {
                if (this.renameInput !== input) return;
                if (confirm && input.value !== this.model.get("_column_name")) {
                    this.send({ event: "column-rename", name: input.value });
                }
                this.closeRename();
                if (confirm === false || document.activeElement === document.body) {
                    this.el.focus({ preventScroll: true });
                }
            };
            input.addEventListener("keydown", event => {
                if (!event.isComposing && ["Enter", "Escape"].includes(event.key)) {
                    event.preventDefault();
                    event.stopPropagation();
                    finish(event.key === "Enter");
                }
            });
            input.addEventListener("blur", () => finish(true));
            heading.append(input);
            input.focus({ preventScroll: true });
            input.select();
        }

        closeRename() {
            const input = this.renameInput;
            this.renameInput = null;
            input?.remove();
        }

        startDrag(event) {
            if (!event.dataTransfer || this.model.get("_pending_delete")) {
                event.preventDefault();
                return;
            }
            this.closeMenu();
            event.dataTransfer.effectAllowed = "move";
            event.dataTransfer.setData("application/x-zizai-column", JSON.stringify({
                source: this.model.get("_column_name"), grid: this.model.get("_grid_id")
            }));
        }

        markDropTarget(event) {
            if (!event.dataTransfer?.types.includes("application/x-zizai-column")) return;
            event.preventDefault();
            event.dataTransfer.dropEffect = "move";
            const after = this.dropAfter(event);
            this.el.classList.toggle("zizai-column-drop-before", !after);
            this.el.classList.toggle("zizai-column-drop-after", after);
            const grid = this.el.closest(".row-preview-grid");
            const bounds = grid.getBoundingClientRect();
            if (event.clientX > bounds.right - 26) grid.scrollLeft += 22;
            if (event.clientX < bounds.left + 26) grid.scrollLeft -= 22;
        }

        dropColumn(event) {
            this.clearDropTarget();
            const payload = event.dataTransfer?.getData("application/x-zizai-column");
            if (!payload) return;
            event.preventDefault();
            let selection;
            try {
                selection = JSON.parse(payload);
            } catch {
                return;
            }
            if (selection?.grid === this.model.get("_grid_id") && typeof selection.source === "string") {
                this.send({ event: "column-move", source: selection.source, after: this.dropAfter(event) });
            }
        }

        dropAfter(event) {
            const header = this.el.getBoundingClientRect();
            return event.clientX >= header.left + header.width / 2;
        }

        clearDropTarget() {
            this.el.classList.remove("zizai-column-drop-before", "zizai-column-drop-after");
        }

        remove() {
            this.closeRename();
            return super.remove();
        }
    }

    return { RowContextView, ColumnContextView };
});
