def pretty_format(obj, base_indent=2, truncate=10) -> str:
    def to_dict(o, indent) -> str:
        if hasattr(o, '__dict__'):
            output = [str(type(o)) + "("]
            for k, v in o.__dict__.items():
                output.append(" "*(indent+base_indent) + k + " = " + to_dict(v, indent + base_indent))

            output.append(" "*indent + ")")
            return "\n".join(output)
        elif isinstance(o, list):
            output = ["["]
            for item in o:
                output.append(" "*(indent+base_indent) + to_dict(item, indent + base_indent))

            output.append(" " * indent + "]")

            return "\n".join(output)
        elif isinstance(o, dict):
            output = ["{"]
            for k,v in o.items():
                try:
                    output.append(" "*(indent+base_indent) + k + " = " + to_dict(v, indent + base_indent))
                except RecursionError:
                    output.append(" " * (indent + base_indent) + k + " = ...")

            output.append(" " * indent + "}")

            return "\n".join(output)
        elif isinstance(o, str):
            o = o.split("\n")
            if 0 < truncate < len(o):
                o = o[:truncate]
                o = "\n".join(o) + '...'
            else:
                o = "\n".join(o)

            return f'"{o}"'
        else:
            return str(o)

    return to_dict(obj, 0)
