define(["@jupyter-widgets/controls"], function (controls) {
    const choices = [
        ["header_row", "ヘッダー行に設定"],
        ["data_start_row", "データ開始行に設定"]
    ];

    class RowContextView extends controls.ButtonView {
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
            const items = choices.map(([role, label]) => {
                const item = document.createElement("button");
                item.type = "button";
                item.setAttribute("role", "menuitem");
                item.textContent = label;
                item.onclick = () => {
                    this.send({ event: "row-role", role });
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

    return { RowContextView };
});
