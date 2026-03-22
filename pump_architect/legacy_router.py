def route_simple_pages(page, render_project_form, render_add_record_wizard, render_add_maintenance_wizard):
    if page == "create":
        render_project_form()
        return True

    if page == "add_record":
        render_add_record_wizard()
        return True

    if page == "add_maintenance":
        render_add_maintenance_wizard()
        return True

    return False
