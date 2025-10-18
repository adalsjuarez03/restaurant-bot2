-- BASE DE DATOS MULTI-RESTAURANTE
DROP DATABASE IF EXISTS sistema_restaurantes;
CREATE DATABASE sistema_restaurantes 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;
USE sistema_restaurantes;

-- TABLA: restaurantes
CREATE TABLE restaurantes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    slug VARCHAR(100) UNIQUE NOT NULL,
    nombre_restaurante VARCHAR(150) NOT NULL,
    descripcion TEXT,
    telefono VARCHAR(20),
    email VARCHAR(100),
    direccion TEXT,
    ciudad VARCHAR(100),
    estado_republica VARCHAR(100),
    codigo_postal VARCHAR(10),
    logo_url VARCHAR(255),
    banner_url VARCHAR(255),
    color_primario VARCHAR(7) DEFAULT '#667eea',
    color_secundario VARCHAR(7) DEFAULT '#764ba2',
    horarios JSON,
    config_delivery JSON,
    bot_token VARCHAR(255) UNIQUE,
    telegram_admin_id BIGINT,
    telegram_group_id BIGINT,
    estado ENUM('activo', 'inactivo', 'prueba', 'suspendido') DEFAULT 'activo',
    plan ENUM('gratis', 'basico', 'premium', 'enterprise') DEFAULT 'gratis',
    fecha_expiracion DATE,
    limite_productos INT DEFAULT 50,
    limite_pedidos_mes INT DEFAULT 100,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_slug (slug),
    INDEX idx_estado (estado),
    INDEX idx_bot_token (bot_token)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- TABLA: usuarios_admin
CREATE TABLE usuarios_admin (
    id INT AUTO_INCREMENT PRIMARY KEY,
    restaurante_id INT NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    nombre_completo VARCHAR(150),
    telefono VARCHAR(20),
    rol ENUM('owner', 'admin', 'manager', 'staff') DEFAULT 'staff',
    activo BOOLEAN DEFAULT TRUE,
    ultimo_acceso TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (restaurante_id) REFERENCES restaurantes(id) ON DELETE CASCADE,
    INDEX idx_restaurante (restaurante_id),
    INDEX idx_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- TABLA: categorias_menu
CREATE TABLE categorias_menu (
    id INT AUTO_INCREMENT PRIMARY KEY,
    restaurante_id INT NOT NULL,
    nombre VARCHAR(50) NOT NULL,
    nombre_display VARCHAR(100),
    descripcion TEXT,
    icono VARCHAR(50),
    orden INT DEFAULT 0,
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (restaurante_id) REFERENCES restaurantes(id) ON DELETE CASCADE,
    INDEX idx_restaurante (restaurante_id),
    INDEX idx_orden (orden)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- TABLA: items_menu
CREATE TABLE items_menu (
    id INT AUTO_INCREMENT PRIMARY KEY,
    restaurante_id INT NOT NULL,
    categoria_id INT NOT NULL,
    codigo VARCHAR(50) NOT NULL,
    nombre VARCHAR(150) NOT NULL,
    descripcion TEXT,
    precio DECIMAL(10,2) NOT NULL,
    imagen_url VARCHAR(255),
    tiempo_preparacion VARCHAR(20),
    disponible BOOLEAN DEFAULT TRUE,
    destacado BOOLEAN DEFAULT FALSE,
    vegano BOOLEAN DEFAULT FALSE,
    vegetariano BOOLEAN DEFAULT FALSE,
    sin_gluten BOOLEAN DEFAULT FALSE,
    picante BOOLEAN DEFAULT FALSE,
    orden INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (restaurante_id) REFERENCES restaurantes(id) ON DELETE CASCADE,
    FOREIGN KEY (categoria_id) REFERENCES categorias_menu(id) ON DELETE CASCADE,
    UNIQUE KEY unique_codigo_restaurante (restaurante_id, codigo),
    INDEX idx_restaurante (restaurante_id),
    INDEX idx_categoria (categoria_id),
    INDEX idx_disponible (disponible)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- TABLA: ingredientes
CREATE TABLE ingredientes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    item_id INT NOT NULL,
    nombre VARCHAR(100) NOT NULL,
    alergeno BOOLEAN DEFAULT FALSE,
    orden INT DEFAULT 0,
    FOREIGN KEY (item_id) REFERENCES items_menu(id) ON DELETE CASCADE,
    INDEX idx_item (item_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- INSERTAR RESTAURANTE DE EJEMPLO
INSERT INTO restaurantes (
    slug, nombre_restaurante, descripcion, telefono, email,
    direccion, ciudad, estado_republica, estado, plan
) VALUES (
    'restaurante-giants',
    'Restaurante Giants',
    'Auténtica cocina italiana con ingredientes frescos',
    '+52 961 123 4567',
    'contacto@giants.com',
    'Av. Central Norte 123',
    'Tuxtla Gutiérrez',
    'Chiapas',
    'activo',
    'premium'
);

-- INSERTAR USUARIO ADMIN (password: admin123)
INSERT INTO usuarios_admin (
    restaurante_id, email, password_hash,
    nombre_completo, telefono, rol
) VALUES (
    1,
    'admin@giants.com',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5pXk.7YzEfY0O',
    'Administrador Giants',
    '+52 961 123 4567',
    'owner'
);

-- INSERTAR CATEGORÍAS DE EJEMPLO
INSERT INTO categorias_menu (restaurante_id, nombre, nombre_display, descripcion, icono, orden) VALUES
(1, 'entradas', '🥗 Entradas', 'Para abrir el apetito', 'salad', 1),
(1, 'principales', '🍖 Platos Principales', 'Nuestros platos estrella', 'restaurant', 2),
(1, 'postres', '🍰 Postres', 'El final perfecto', 'cake', 3),
(1, 'bebidas', '🥤 Bebidas', 'Para acompañar', 'local-cafe', 4),
(1, 'especialidades', '⭐ Especialidades', 'Lo mejor de la casa', 'star', 5);

-- INSERTAR ITEMS DE EJEMPLO
INSERT INTO items_menu (restaurante_id, categoria_id, codigo, nombre, descripcion, precio, tiempo_preparacion, disponible, vegano) VALUES
(1, 1, 'bruschetta', 'Bruschetta Clásica', 'Pan tostado con tomate fresco, albahaca y ajo', 120.00, '5-8 min', TRUE, TRUE),
(1, 1, 'antipasto', 'Antipasto Italiano', 'Selección de quesos, carnes frías y aceitunas', 180.00, '5 min', TRUE, FALSE),
(1, 1, 'caprese', 'Ensalada Caprese', 'Mozzarella fresca, tomate y albahaca', 150.00, '5 min', TRUE, TRUE),
(1, 2, 'carbonara', 'Spaghetti Carbonara', 'Pasta con huevo, pancetta y queso parmesano', 220.00, '12-15 min', TRUE, FALSE),
(1, 2, 'margherita', 'Pizza Margherita', 'Pizza clásica con tomate, mozzarella y albahaca', 200.00, '15-18 min', TRUE, FALSE),
(1, 2, 'lasagna', 'Lasagna de la Casa', 'Lasagna con carne, salsa boloñesa y bechamel', 280.00, '20-25 min', TRUE, FALSE),
(1, 2, 'ossobuco', 'Ossobuco alla Milanese', 'Osobuco de ternera con risotto', 380.00, '35-40 min', FALSE, FALSE),
(1, 3, 'tiramisu', 'Tiramisú Casero', 'El clásico postre italiano con café y mascarpone', 120.00, '5 min', TRUE, FALSE),
(1, 3, 'gelato', 'Gelato Artesanal', 'Helado artesanal (vainilla, fresa, chocolate)', 80.00, '3 min', TRUE, FALSE),
(1, 3, 'cannoli', 'Cannoli Siciliano', 'Tradicional cannoli relleno de ricotta y chocolate', 100.00, '5 min', TRUE, FALSE),
(1, 4, 'espresso', 'Espresso Italiano', 'Café espresso auténtico italiano', 45.00, '3 min', TRUE, TRUE),
(1, 4, 'cappuccino', 'Cappuccino', 'Espresso con leche espumosa', 60.00, '5 min', TRUE, FALSE),
(1, 4, 'chianti', 'Vino Chianti (Copa)', 'Vino tinto italiano de la Toscana', 120.00, '2 min', TRUE, TRUE),
(1, 4, 'limonada', 'Limonada Italiana', 'Refresco de limón con hierbas frescas', 55.00, '3 min', TRUE, TRUE),
(1, 5, 'pasta_trufa', 'Pasta con Trufa Negra', 'Fettuccine con trufa negra y parmesano', 450.00, '18-20 min', TRUE, FALSE),
(1, 5, 'branzino', 'Branzino al Sale', 'Lubina mediterránea en costra de sal con verduras', 380.00, '25-30 min', TRUE, FALSE);

-- INSERTAR INGREDIENTES
INSERT INTO ingredientes (item_id, nombre, alergeno, orden) VALUES
-- Bruschetta
(1, 'Pan artesanal', FALSE, 1),
(1, 'Tomate fresco', FALSE, 2),
(1, 'Albahaca', FALSE, 3),
(1, 'Ajo', FALSE, 4),
(1, 'Aceite de oliva', FALSE, 5),
-- Carbonara
(4, 'Spaghetti', TRUE, 1),
(4, 'Huevo', TRUE, 2),
(4, 'Pancetta', FALSE, 3),
(4, 'Queso parmesano', TRUE, 4),
(4, 'Pimienta negra', FALSE, 5);