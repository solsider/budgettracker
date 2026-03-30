document.addEventListener("DOMContentLoaded", () => {
    const typeInputs = document.querySelectorAll(".transaction-type");
    const categorySelect = document.getElementById("category-select");

    if (!typeInputs.length || !categorySelect) {
        return;
    }

    const syncCategories = () => {
        const selectedType = document.querySelector(".transaction-type:checked")?.value;
        let firstVisibleOption = null;
        let hasActiveSelection = false;

        Array.from(categorySelect.options).forEach((option) => {
            const shouldShow = option.dataset.type === selectedType;
            option.hidden = !shouldShow;

            if (shouldShow && !firstVisibleOption) {
                firstVisibleOption = option;
            }

            if (shouldShow && option.selected) {
                hasActiveSelection = true;
            }
        });

        if (!hasActiveSelection && firstVisibleOption) {
            firstVisibleOption.selected = true;
        }
    };

    typeInputs.forEach((input) => input.addEventListener("change", syncCategories));
    syncCategories();
});
