#!/usr/bin/env python3
"""Script para generar una estructura de directorios condensada,
agrupando archivos similares y directorios de imágenes para mejor visualización.
"""

from collections import Counter, defaultdict
import os
import re


def add_note(line, notes):
    """Añade una nota al final de la línea si existe en el diccionario de notas"""
    for pattern, note in notes.items():
        if re.search(pattern, line):
            return f"{line} {note}"
    return line

def get_base_name(filename):
    """Extrae el nombre base del archivo sin la extensión"""
    return os.path.splitext(filename)[0]

def get_extension(filename):
    """Obtiene la extensión del archivo"""
    return os.path.splitext(filename)[1].lower()

def is_image_file(filename):
    """Determina si un archivo es una imagen basado en su extensión"""
    image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico", ".bmp", ".tiff"}
    return get_extension(filename) in image_extensions

def is_image_directory(files):
    """Determina si un directorio contiene principalmente imágenes"""
    if not files:
        return False

    image_count = sum(1 for f in files if is_image_file(f))
    return image_count / len(files) >= 0.5  # Si más del 50% son imágenes

def should_condense(files, threshold=10, is_img_dir=False):
    """Determina si un conjunto de archivos debe condensarse basado en patrones similares
    y aplica un umbral más bajo para directorios de imágenes
    """
    # Umbral más bajo para directorios de imágenes
    if is_img_dir:
        threshold = min(threshold, 5)  # Aplica un umbral más bajo para imágenes

    if len(files) < threshold:
        return False

    # Analizar patrones en los nombres de archivos
    extensions = Counter([get_extension(f) for f in files])

    # Buscar patrones comunes en nombres de archivos
    prefixes = Counter()
    for file in files:
        base = get_base_name(file)
        prefix = "-".join(base.split("-")[:-1]) if "-" in base else base
        prefixes[prefix] += 1

    # Si hay muchos archivos con el mismo prefijo o extensión, condensar
    return any(count >= threshold/2 for count in extensions.values()) or \
           any(count >= threshold/2 for count in prefixes.values())

def should_exclude_dir(dir_path, exclude_dirs):
    """Verifica si un directorio debe ser excluido basado en su nombre o ruta"""
    dir_name = os.path.basename(dir_path)

    # Verificar exclusión por nombre de directorio
    if dir_name in exclude_dirs:
        return True

    # Verificar exclusión por parte de la ruta
    for excluded in exclude_dirs:
        if excluded in dir_path.split(os.sep):
            return True

    return False

def generate_directory_tree(start_path=".", output_file="directory_structure.txt", exclude_dirs=None, notes=None, condensation_threshold=10, max_depth=None):
    """Genera un archivo de texto con la estructura de directorios mejorada y condensada
    
    Args:
        start_path: Directorio inicial para comenzar la exploración
        output_file: Nombre del archivo donde se guardará la estructura
        exclude_dirs: Lista de directorios a excluir
        notes: Diccionario con patrones de archivos y notas a añadir
        condensation_threshold: Número mínimo de archivos para considerar condensación
        max_depth: Profundidad máxima a recorrer (None para sin límite)
    """
    if exclude_dirs is None:
        exclude_dirs = ["venv", "__pycache__", ".git", ".idea", "node_modules", "dist", "build"]

    if notes is None:
        notes = {}

    # Obtener el nombre del directorio raíz
    root_name = os.path.basename(os.path.abspath(start_path))

    # Estructura para almacenar el árbol de directorios
    tree = {}

    # Recopilar la estructura de directorios
    for root, dirs, files in os.walk(start_path):
        # Calcular la profundidad relativa
        rel_path = os.path.relpath(root, start_path)
        depth = 0 if rel_path == "." else len(rel_path.split(os.sep))

        # Si se ha alcanzado la profundidad máxima, no seguir descendiendo
        if max_depth is not None and depth >= max_depth:
            dirs[:] = []  # No seguir procesando subdirectorios
            continue

        # Excluir directorios no deseados
        dirs[:] = [d for d in dirs if not should_exclude_dir(os.path.join(root, d), exclude_dirs)]

        # Excluir archivos ocultos y .DS_Store
        files = [f for f in files if not f.startswith(".") and f != ".DS_Store"]

        # Determinar si es un directorio de imágenes
        is_img_dir = is_image_directory(files)

        # Agrupar archivos por nombre base (sin extensión)
        files_by_base = defaultdict(list)
        for file in files:
            base_name = get_base_name(file)
            files_by_base[base_name].append(file)

        # Almacenar en la estructura
        if rel_path == ".":
            tree[root_name] = {"dirs": {}, "files": files_by_base, "all_files": files, "is_img_dir": is_img_dir}
        else:
            # Navegar por el árbol para encontrar el directorio correcto
            current = tree[root_name]
            parts = rel_path.split(os.sep)

            for part in parts:
                # Verificar si el directorio debe ser excluido
                if should_exclude_dir(os.path.join(start_path, *parts[:parts.index(part)+1]), exclude_dirs):
                    break

                if part not in current["dirs"]:
                    current["dirs"][part] = {"dirs": {}, "files": {}, "all_files": [], "is_img_dir": False}
                current = current["dirs"][part]
            else:  # Este bloque se ejecuta solo si no hubo break
                current["files"] = files_by_base
                current["all_files"] = files
                current["is_img_dir"] = is_img_dir

    # Escribir el árbol a un archivo
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"{root_name}/\n")
        write_tree(f, tree[root_name], "", notes, condensation_threshold)

    print(f"Estructura de directorios guardada en '{output_file}'")

def analyze_patterns(files):
    """Analiza patrones en los nombres de archivos para agruparlos mejor"""
    patterns = {}

    # Buscar patrones por extensión
    by_extension = defaultdict(list)
    for f in files:
        ext = get_extension(f)
        by_extension[ext].append(f)

    # Buscar patrones por prefijo común
    by_prefix = defaultdict(list)
    for f in files:
        base = get_base_name(f)
        prefix = "-".join(base.split("-")[:-1]) if "-" in base else ""
        if prefix:
            by_prefix[prefix].append(f)

    # Determinar el mejor método para condensar
    if len(by_extension) < len(by_prefix) and any(len(files) > 3 for files in by_extension.values()):
        for ext, files_list in by_extension.items():
            if len(files_list) > 3:
                patterns[f"*{ext}"] = files_list
    elif any(len(files) > 3 for files in by_prefix.values()):
        for prefix, files_list in by_prefix.items():
            if len(files_list) > 3:
                patterns[f"{prefix}-*"] = files_list

    # Si todos los archivos son imágenes con la misma extensión, condensa todo el directorio
    if len(by_extension) == 1 and all(is_image_file(f) for f in files):
        ext = list(by_extension.keys())[0]
        patterns = {f"*{ext}": files}

    return patterns

def condense_image_directory(files):
    """Condensa un directorio de imágenes en un solo patrón"""
    extensions = Counter([get_extension(f) for f in files])
    most_common_ext = extensions.most_common(1)[0][0] if extensions else ""

    if most_common_ext:
        return {f"*{most_common_ext}": [f for f in files if f.endswith(most_common_ext)]}
    return {}

def write_tree(file, node, prefix, notes, condensation_threshold):
    """Escribe la estructura del árbol en el archivo
    con una visualización jerárquica correcta y condensada
    """
    # Ordenar directorios y archivos para una visualización consistente
    dirs = sorted(node["dirs"].keys())

    # Determinar si es un directorio de imágenes
    is_img_dir = node["is_img_dir"]

    # Preparar la condensación
    all_files = node["all_files"]
    condensed_patterns = {}

    # Aplicar diferentes estrategias según el tipo de directorio
    if is_img_dir:
        # Si es un directorio de imágenes, usar un umbral más bajo
        if should_condense(all_files, condensation_threshold, is_img_dir=True):
            condensed_patterns = condense_image_directory(all_files)
    elif should_condense(all_files, condensation_threshold):
        condensed_patterns = analyze_patterns(all_files)

    # Eliminar archivos ya condensados
    condensed_files = set()
    for pattern_files in condensed_patterns.values():
        condensed_files.update(pattern_files)

    # Actualizar los grupos de archivos - mantenemos esto como diccionario
    file_dict = {}
    for base, files in node["files"].items():
        remaining = [f for f in files if f not in condensed_files]
        if remaining:
            file_dict[base] = remaining

    # Usamos una lista ordenada de las claves del diccionario
    file_groups = sorted(file_dict.keys())

    total_items = len(dirs) + len(file_groups) + len(condensed_patterns)
    current_item = 0

    # Escribir directorios
    for idx, dir_name in enumerate(dirs):
        current_item += 1
        is_last = current_item == total_items

        if is_last and total_items > 0:
            file.write(f"{prefix}└── {dir_name}/\n")
            new_prefix = prefix + "    "
        else:
            file.write(f"{prefix}├── {dir_name}/\n")
            new_prefix = prefix + "│   "

        # Recursivamente escribir el contenido del directorio
        write_tree(file, node["dirs"][dir_name], new_prefix, notes, condensation_threshold)

    # Escribir patrones condensados
    for pattern, files in condensed_patterns.items():
        current_item += 1
        is_last = current_item == total_items

        count = len(files)
        if is_last:
            line = f"{prefix}└── {pattern} ({count} archivos)"
        else:
            line = f"{prefix}├── {pattern} ({count} archivos)"

        # Añadir nota si existe
        file.write(f"{line}\n")

    # Escribir grupos de archivos individuales - ahora usando correctamente el diccionario
    for base_name in file_groups:
        files = sorted(file_dict[base_name])  # Usamos file_dict en lugar de file_groups

        for file_idx, filename in enumerate(files):
            current_item += 1
            is_last_file = current_item == total_items

            if is_last_file:
                line = f"{prefix}└── {filename}"
            else:
                line = f"{prefix}├── {filename}"

            # Añadir nota si existe
            line_with_note = add_note(line, notes)
            file.write(f"{line_with_note}\n")

def simple_directory_structure(start_path=".", output_file="directory_structure.txt", exclude_dirs=None, notes=None):
    """Genera una estructura de directorios simplificada, similar al ejemplo proporcionado.
    Solo muestra directorios y archivos hasta cierta profundidad, sin detallar el contenido interno.
    
    Args:
        start_path: Directorio inicial para comenzar la exploración
        output_file: Nombre del archivo donde se guardará la estructura
        exclude_dirs: Lista de directorios a excluir completamente
        notes: Diccionario con patrones de archivos y notas a añadir
    """
    if exclude_dirs is None:
        exclude_dirs = ["node_modules", "dist", "build", ".next", ".cache", "coverage", "__pycache__"]

    if notes is None:
        notes = {}

    # Lista para almacenar la estructura
    lines = []
    root_name = os.path.basename(os.path.abspath(start_path))
    lines.append(f"{root_name}/")

    # Obtener directorios y archivos de primer nivel
    try:
        items = sorted(os.listdir(start_path))
    except PermissionError:
        print(f"Error: No se puede acceder a {start_path}")
        return

    # Separar archivos y directorios
    dirs = []
    files = []

    for item in items:
        full_path = os.path.join(start_path, item)
        # Excluir directorios no deseados y archivos ocultos
        if item in exclude_dirs or item.startswith(".") or item == ".DS_Store":
            continue

        if os.path.isdir(full_path):
            if not should_exclude_dir(full_path, exclude_dirs):
                dirs.append(item)
        else:
            files.append(item)

    # Procesar archivos de primer nivel
    total_items = len(dirs) + len(files)
    for idx, filename in enumerate(sorted(files)):
        is_last = idx == total_items - 1

        if is_last:
            line = f"└── {filename}"
        else:
            line = f"├── {filename}"

        # Añadir nota si existe
        for pattern, note in notes.items():
            if re.search(pattern, filename):
                line += f" {note}"
                break

        lines.append(line)

    # Procesar directorios de primer nivel
    for idx, dirname in enumerate(sorted(dirs)):
        is_last_dir = idx == len(dirs) - 1

        if is_last_dir and len(files) == 0:
            prefix = "└── "
            child_prefix = "    "
        else:
            prefix = "├── "
            child_prefix = "│   "

        lines.append(f"{prefix}{dirname}/")

        # Procesar el contenido del directorio actual (solo un nivel)
        dir_path = os.path.join(start_path, dirname)
        process_directory_contents(dir_path, lines, child_prefix, exclude_dirs, notes)

    # Escribir el resultado en el archivo
    with open(output_file, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(f"{line}\n")

    print(f"Estructura de directorios simplificada guardada en '{output_file}'")

def process_directory_contents(dir_path, lines, prefix, exclude_dirs, notes):
    """Procesa los contenidos de un directorio para la estructura simplificada
    """
    try:
        items = sorted(os.listdir(dir_path))
    except (PermissionError, FileNotFoundError):
        lines.append(f"{prefix}└── (sin acceso o no encontrado)")
        return

    # Filtrar elementos excluidos
    items = [item for item in items if item not in exclude_dirs and not item.startswith(".") and item != ".DS_Store"]

    # Para directorios como __pycache__, solo mostrar el nombre sin entrar en detalle
    if os.path.basename(dir_path) == "__pycache__" or "pycache" in dir_path:
        return

    # Separar archivos y directorios
    dirs = []
    files = []

    for item in items:
        full_path = os.path.join(dir_path, item)
        if os.path.isdir(full_path):
            if not should_exclude_dir(full_path, exclude_dirs):
                dirs.append(item)
        else:
            files.append(item)

    # Procesar archivos
    for idx, filename in enumerate(sorted(files)):
        is_last = idx == len(files) - 1 and len(dirs) == 0

        if is_last:
            line = f"{prefix}└── {filename}"
        else:
            line = f"{prefix}├── {filename}"

        # Añadir nota si existe
        for pattern, note in notes.items():
            if re.search(pattern, filename):
                line += f" {note}"
                break

        lines.append(line)

    # Mostrar directorios solo hasta cierto nivel sin entrar en su contenido
    for idx, dirname in enumerate(sorted(dirs)):
        is_last = idx == len(dirs) - 1

        if is_last:
            line = f"{prefix}└── {dirname}/"
        else:
            line = f"{prefix}├── {dirname}/"

        lines.append(line)

if __name__ == "__main__":
    # Define notas para archivos específicos
    file_notes = {
        r"app\.py$": "✅ actualizado con blueprint integrations",
        r"index\.html$": "✅ SEO optimizado",
        r"SheetsViewer\.jsx$": "✅ NUEVO",
        r"useGoogleSheets\.js$": "✅ NUEVO — consumo de Google Sheets desde frontend",
        r"integrations\.py$": "✅ NUEVO — endpoints Google Sheets, Notion, Trello",
        # Añade más notas según sea necesario
    }

    # Directorios a excluir completamente
    exclude = [
        "venv", "node_modules", "dist", "build", ".next", ".cache",
        "coverage", ".git", "__pycache__", ".DS_Store", ".pytest_cache",
        "migrations/versions"  # Excluir versiones de migraciones
    ]

    # Utilizar la versión simplificada para obtener una salida más limpia y similar al ejemplo
    simple_directory_structure(
        start_path=".",  # Directorio actual
        output_file="estructura_proyecto.txt",
        exclude_dirs=exclude,
        notes=file_notes
    )

    # Opcional: También puedes ejecutar la versión detallada con límite de profundidad
    """
    generate_directory_tree(
        start_path='.',
        output_file='estructura_detallada.txt',
        exclude_dirs=exclude,
        notes=file_notes,
        condensation_threshold=8,
        max_depth=2  # Limitar a 2 niveles de profundidad
    )
    """
