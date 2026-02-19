"""Tests for Java parser module."""

import pytest
import struct
import tempfile
from pathlib import Path

from cqviewer.parser.java_parser import (
    parse_java_source, parse_java_class, parse_java_file,
    java_type_to_schema_type, java_fields_to_schema, merge_schemas,
    JavaField, extract_inner_classes, parse_java_source_with_inner_classes,
    scan_directory_for_java_files, parse_directory, ClassRegistry,
    detect_encoding_from_source, extract_thrift_field_ids,
)
from cqviewer.parser.schema import Schema, MessageDef, FieldDef, ENCODING_BINARY, ENCODING_SBE


class TestJavaTypeMapping:
    """Tests for Java to schema type mapping."""

    def test_primitive_types(self):
        assert java_type_to_schema_type("byte") == "int8"
        assert java_type_to_schema_type("short") == "int16"
        assert java_type_to_schema_type("int") == "int32"
        assert java_type_to_schema_type("long") == "int64"
        assert java_type_to_schema_type("float") == "float32"
        assert java_type_to_schema_type("double") == "float64"
        assert java_type_to_schema_type("boolean") == "bool"
        assert java_type_to_schema_type("char") == "uint16"

    def test_wrapper_types(self):
        assert java_type_to_schema_type("Integer") == "int32"
        assert java_type_to_schema_type("Long") == "int64"
        assert java_type_to_schema_type("Double") == "float64"
        assert java_type_to_schema_type("Boolean") == "bool"

    def test_string_types(self):
        assert java_type_to_schema_type("String") == "string"
        assert java_type_to_schema_type("CharSequence") == "string"

    def test_byte_array(self):
        assert java_type_to_schema_type("byte[]") == "bytes"

    def test_unknown_types(self):
        # Unknown object types default to "object" for nested struct handling
        assert java_type_to_schema_type("CustomObject") == "object"
        assert java_type_to_schema_type("List") == "object"


class TestParseJavaSource:
    """Tests for parsing Java source files."""

    def test_parse_simple_fields(self):
        java_code = """
        public class Order {
            private long orderId;
            private String symbol;
            private int quantity;
            private double price;
        }
        """
        with tempfile.NamedTemporaryFile(suffix=".java", mode="w", delete=False) as f:
            f.write(java_code)
            f.flush()

            class_name, fields, encoding = parse_java_source(f.name)

        assert class_name == "Order"
        assert len(fields) == 4
        assert encoding == "binary"  # Default encoding for simple classes
        names = [f.name for f in fields]
        assert "orderId" in names
        assert "symbol" in names
        assert "quantity" in names
        assert "price" in names

    def test_parse_with_initializers(self):
        java_code = """
        public class Config {
            private int count = 0;
            private String name = "default";
            private double rate = 1.5;
        }
        """
        with tempfile.NamedTemporaryFile(suffix=".java", mode="w", delete=False) as f:
            f.write(java_code)
            f.flush()

            class_name, fields, _ = parse_java_source(f.name)

        assert class_name == "Config"
        assert len(fields) == 3
        names = [f.name for f in fields]
        assert "count" in names
        assert "name" in names
        assert "rate" in names

    def test_parse_static_fields(self):
        java_code = """
        public class Constants {
            private static int STATIC_VAL = 42;
            private int instanceVal;
        }
        """
        with tempfile.NamedTemporaryFile(suffix=".java", mode="w", delete=False) as f:
            f.write(java_code)
            f.flush()

            class_name, fields, _ = parse_java_source(f.name)

        static_fields = [f for f in fields if f.is_static]
        instance_fields = [f for f in fields if not f.is_static]

        assert len(static_fields) >= 1
        assert len(instance_fields) >= 1

    def test_parse_transient_fields(self):
        java_code = """
        public class Session {
            private long sessionId;
            private transient String tempData;
        }
        """
        with tempfile.NamedTemporaryFile(suffix=".java", mode="w", delete=False) as f:
            f.write(java_code)
            f.flush()

            class_name, fields, _ = parse_java_source(f.name)

        transient_fields = [f for f in fields if f.is_transient]
        assert len(transient_fields) >= 1

    def test_parse_ignores_comments(self):
        java_code = """
        public class Test {
            // private int commented;
            private int actual;
            /* private int blockCommented; */
        }
        """
        with tempfile.NamedTemporaryFile(suffix=".java", mode="w", delete=False) as f:
            f.write(java_code)
            f.flush()

            class_name, fields, _ = parse_java_source(f.name)

        names = [f.name for f in fields]
        assert "actual" in names
        # Commented fields should not appear
        assert "commented" not in names
        assert "blockCommented" not in names

    def test_parse_various_modifiers(self):
        java_code = """
        public class Mixed {
            public long publicField;
            protected int protectedField;
            private String privateField;
            double packageField;
            final int finalField = 1;
            volatile boolean volatileField;
        }
        """
        with tempfile.NamedTemporaryFile(suffix=".java", mode="w", delete=False) as f:
            f.write(java_code)
            f.flush()

            class_name, fields, _ = parse_java_source(f.name)

        names = [f.name for f in fields]
        assert "publicField" in names
        assert "protectedField" in names
        assert "privateField" in names


class TestJavaFieldsToSchema:
    """Tests for converting Java fields to Schema."""

    def test_basic_conversion(self):
        fields = [
            JavaField(name="id", java_type="long"),
            JavaField(name="price", java_type="double"),
            JavaField(name="name", java_type="String"),
        ]

        schema = java_fields_to_schema("Order", fields)

        assert "Order" in schema.messages
        assert schema.default_message == "Order"
        assert len(schema.messages["Order"].fields) == 3

    def test_excludes_static_by_default(self):
        fields = [
            JavaField(name="instance", java_type="int"),
            JavaField(name="STATIC", java_type="int", is_static=True),
        ]

        schema = java_fields_to_schema("Test", fields)

        field_names = [f.name for f in schema.messages["Test"].fields]
        assert "instance" in field_names
        assert "STATIC" not in field_names

    def test_excludes_transient_by_default(self):
        fields = [
            JavaField(name="persisted", java_type="int"),
            JavaField(name="temp", java_type="int", is_transient=True),
        ]

        schema = java_fields_to_schema("Test", fields)

        field_names = [f.name for f in schema.messages["Test"].fields]
        assert "persisted" in field_names
        assert "temp" not in field_names

    def test_include_static_when_requested(self):
        fields = [
            JavaField(name="instance", java_type="int"),
            JavaField(name="STATIC", java_type="int", is_static=True),
        ]

        schema = java_fields_to_schema("Test", fields, include_static=True)

        field_names = [f.name for f in schema.messages["Test"].fields]
        assert "instance" in field_names
        assert "STATIC" in field_names


class TestMergeSchemas:
    """Tests for merging multiple schemas."""

    def test_merge_two_schemas(self):
        # Create proper MessageDef objects
        order_def = MessageDef(name="Order", fields=[
            FieldDef(name="orderId", type="int64"),
            FieldDef(name="item", type="object"),  # Has nested object
        ])
        trade_def = MessageDef(name="Trade", fields=[
            FieldDef(name="tradeId", type="int64"),
        ])

        schema1 = Schema(
            messages={"Order": order_def},
            default_message="Order"
        )
        schema2 = Schema(
            messages={"Trade": trade_def},
            default_message=None
        )

        merged = merge_schemas(schema1, schema2)

        assert "Order" in merged.messages
        assert "Trade" in merged.messages
        # Order has nested object, so it should be preferred
        assert merged.default_message == "Order"

    def test_merge_picks_message_with_nested_objects(self):
        # Main type has a nested object reference
        main_def = MessageDef(name="Main", fields=[
            FieldDef(name="header", type="object"),
            FieldDef(name="data", type="string"),
        ])
        # Helper type has no nested objects
        helper_def = MessageDef(name="Helper", fields=[
            FieldDef(name="id", type="int64"),
            FieldDef(name="name", type="string"),
            FieldDef(name="value", type="float64"),
        ])

        schema1 = Schema(messages={"Helper": helper_def}, default_message="Helper")
        schema2 = Schema(messages={"Main": main_def}, default_message="Main")

        merged = merge_schemas(schema1, schema2)

        # Main should be picked because it has nested object, even though Helper was first
        assert merged.default_message == "Main"


class TestParseJavaFile:
    """Tests for the unified parse_java_file function."""

    def test_parse_java_source_file(self):
        java_code = """
        public class FxTick {
            private long timestamp;
            private double bid;
            private double ask;
        }
        """
        with tempfile.NamedTemporaryFile(suffix=".java", mode="w", delete=False) as f:
            f.write(java_code)
            f.flush()

            schema = parse_java_file(f.name)

        assert "FxTick" in schema.messages
        field_names = [f.name for f in schema.messages["FxTick"].fields]
        assert "timestamp" in field_names
        assert "bid" in field_names
        assert "ask" in field_names

    def test_unsupported_extension(self):
        with pytest.raises(ValueError, match="Unsupported file type"):
            parse_java_file("test.txt")


class TestEndToEnd:
    """End-to-end tests for Java parsing and schema creation."""

    def test_full_workflow(self):
        """Test parsing a Java file and using the schema."""
        java_code = """
        package com.example;

        public class TradeEvent {
            private long tradeId;
            private long timestamp;
            private String symbol;
            private double price;
            private int quantity;
            private boolean isBuy;

            // Transient fields should be excluded
            private transient String tempBuffer;

            // Static fields should be excluded
            private static int counter = 0;
        }
        """
        with tempfile.NamedTemporaryFile(suffix=".java", mode="w", delete=False) as f:
            f.write(java_code)
            f.flush()

            schema = parse_java_file(f.name)

        # Check the schema
        assert schema.default_message == "TradeEvent"
        msg = schema.messages["TradeEvent"]

        field_names = [f.name for f in msg.fields]
        field_types = {f.name: f.type for f in msg.fields}

        # Instance fields should be present
        assert "tradeId" in field_names
        assert "timestamp" in field_names
        assert "symbol" in field_names
        assert "price" in field_names
        assert "quantity" in field_names
        assert "isBuy" in field_names

        # Static and transient should be excluded
        assert "tempBuffer" not in field_names
        assert "counter" not in field_names

        # Check types
        assert field_types["tradeId"] == "int64"
        assert field_types["timestamp"] == "int64"
        assert field_types["symbol"] == "string"
        assert field_types["price"] == "float64"
        assert field_types["quantity"] == "int32"
        assert field_types["isBuy"] == "bool"


class TestClassRegistry:
    """Tests for ClassRegistry."""

    def test_register_and_get(self):
        registry = ClassRegistry()
        schema = Schema(default_message="TestClass")

        registry.register("com.example.TestClass", schema)

        # Should get by fully-qualified name
        assert registry.get("com.example.TestClass") is schema
        # Should also get by simple name
        assert registry.get("TestClass") is schema

    def test_merge_all(self):
        registry = ClassRegistry()
        class1_def = MessageDef(name="Class1", fields=[FieldDef(name="id", type="int64")])
        class2_def = MessageDef(name="Class2", fields=[FieldDef(name="name", type="string")])
        schema1 = Schema(messages={"Class1": class1_def}, default_message="Class1")
        schema2 = Schema(messages={"Class2": class2_def}, default_message="Class2")

        registry.register("Class1", schema1)
        registry.register("Class2", schema2)

        merged = registry.merge_all()
        assert "Class1" in merged.messages
        assert "Class2" in merged.messages


class TestExtractInnerClasses:
    """Tests for extracting inner classes from Java source."""

    def test_extract_simple_inner_class(self):
        java_code = """
        public class Order {
            private long orderId;

            public static class Item {
                private String productId;
                private int quantity;
            }
        }
        """

        inner_classes = extract_inner_classes(java_code, "Order")

        assert len(inner_classes) == 1
        assert inner_classes[0][0] == "Item"

    def test_extract_multiple_inner_classes(self):
        java_code = """
        public class Order {
            private long orderId;

            public static class Item {
                private String productId;
            }

            public static class Address {
                private String street;
                private String city;
            }
        }
        """

        inner_classes = extract_inner_classes(java_code, "Order")

        assert len(inner_classes) == 2
        names = [ic[0] for ic in inner_classes]
        assert "Item" in names
        assert "Address" in names

    def test_does_not_include_outer_class(self):
        java_code = """
        public class Outer {
            private int field;
        }
        """

        inner_classes = extract_inner_classes(java_code, "Outer")
        names = [ic[0] for ic in inner_classes]
        assert "Outer" not in names


class TestParseJavaSourceWithInnerClasses:
    """Tests for parsing Java source including inner classes."""

    def test_parse_with_inner_class(self):
        java_code = """
        public class Order {
            private long orderId;
            private Item item;

            public static class Item {
                private String productId;
                private int quantity;
            }
        }
        """
        with tempfile.NamedTemporaryFile(suffix=".java", mode="w", delete=False) as f:
            f.write(java_code)
            f.flush()

            main_schema, inner_schemas = parse_java_source_with_inner_classes(f.name)

        # Check main class
        assert main_schema.default_message == "Order"
        main_fields = [f.name for f in main_schema.messages["Order"].fields]
        assert "orderId" in main_fields

        # Check inner class
        assert len(inner_schemas) == 1
        inner_schema = inner_schemas[0]
        assert inner_schema.default_message == "Item"
        inner_fields = [f.name for f in inner_schema.messages["Item"].fields]
        assert "productId" in inner_fields
        assert "quantity" in inner_fields


class TestScanDirectory:
    """Tests for directory scanning."""

    def test_scan_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            files = scan_directory_for_java_files(tmpdir)
            assert len(files) == 0

    def test_scan_directory_with_java_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create some Java files
            (tmppath / "Order.java").write_text("public class Order {}")
            (tmppath / "Trade.java").write_text("public class Trade {}")

            files = scan_directory_for_java_files(tmpdir)

            assert len(files) == 2
            names = [f.name for f in files]
            assert "Order.java" in names
            assert "Trade.java" in names

    def test_scan_directory_recursive(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create nested directory structure
            subdir = tmppath / "model"
            subdir.mkdir()

            (tmppath / "Root.java").write_text("public class Root {}")
            (subdir / "Nested.java").write_text("public class Nested {}")

            files = scan_directory_for_java_files(tmpdir)

            assert len(files) == 2
            names = [f.name for f in files]
            assert "Root.java" in names
            assert "Nested.java" in names

    def test_scan_invalid_directory(self):
        with pytest.raises(ValueError, match="Not a directory"):
            scan_directory_for_java_files("/nonexistent/path")


class TestParseDirectory:
    """Tests for parsing an entire directory."""

    def test_parse_directory_single_file(self):
        java_code = """
        public class Order {
            private long orderId;
            private String symbol;
        }
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "Order.java").write_text(java_code)

            schema = parse_directory(tmpdir)

        assert "Order" in schema.messages
        fields = [f.name for f in schema.messages["Order"].fields]
        assert "orderId" in fields
        assert "symbol" in fields

    def test_parse_directory_multiple_files(self):
        order_code = """
        public class Order {
            private long orderId;
        }
        """
        trade_code = """
        public class Trade {
            private long tradeId;
        }
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "Order.java").write_text(order_code)
            (tmppath / "Trade.java").write_text(trade_code)

            schema = parse_directory(tmpdir)

        assert "Order" in schema.messages
        assert "Trade" in schema.messages

    def test_parse_directory_with_inner_classes(self):
        java_code = """
        public class Order {
            private long orderId;
            private Item item;

            public static class Item {
                private String productId;
                private int quantity;
            }
        }
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "Order.java").write_text(java_code)

            schema = parse_directory(tmpdir, include_inner_classes=True)

        # Should have both Order and Item
        assert "Order" in schema.messages
        assert "Item" in schema.messages

        # Check Item fields
        item_fields = [f.name for f in schema.messages["Item"].fields]
        assert "productId" in item_fields
        assert "quantity" in item_fields

    def test_parse_directory_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(ValueError, match="No .java or .class files found"):
                parse_directory(tmpdir)


class TestDetectEncoding:
    """Tests for encoding auto-detection."""

    def test_detect_binary_default(self):
        """Test that plain Java source defaults to binary encoding."""
        code = "public class Order { private long id; }"
        assert detect_encoding_from_source(code) == ENCODING_BINARY

    def test_detect_sbe_from_import(self):
        """Test SBE detection from import statement."""
        code = "import uk.co.real_logic.sbe.codec.Encoder;"
        assert detect_encoding_from_source(code) == ENCODING_SBE

    def test_detect_sbe_from_annotation(self):
        """Test SBE detection from @SbeField annotation."""
        code = "@SbeField(name = \"orderId\") private long orderId;"
        assert detect_encoding_from_source(code) == ENCODING_SBE

    def test_detect_sbe_from_header_encoder(self):
        """Test SBE detection from MessageHeaderEncoder usage."""
        code = "MessageHeaderEncoder headerEncoder = new MessageHeaderEncoder();"
        assert detect_encoding_from_source(code) == ENCODING_SBE

    def test_thrift_not_auto_detected(self):
        """Test that Thrift classes are NOT auto-detected (defaults to binary)."""
        code = """
        import org.apache.thrift.TBase;
        public class Order extends TBase {
            private long orderId;
        }
        """
        # Per the source code design: Thrift classes default to binary
        assert detect_encoding_from_source(code) == ENCODING_BINARY


class TestExtractThriftFieldIds:
    """Tests for extracting Thrift field IDs."""

    def test_extract_tfield_declarations(self):
        """Test extracting TField ID declarations."""
        code = """
        private static final org.apache.thrift.protocol.TField APP_ID_FIELD_DESC =
            new org.apache.thrift.protocol.TField("appId", org.apache.thrift.protocol.TType.STRING, (short)2);
        private static final org.apache.thrift.protocol.TField SESSION_ID_FIELD_DESC =
            new org.apache.thrift.protocol.TField("sessionId", org.apache.thrift.protocol.TType.I64, (short)3);
        """
        ids = extract_thrift_field_ids(code)
        assert ids["appId"] == 2
        assert ids["sessionId"] == 3

    def test_extract_no_tfield(self):
        """Test extraction from code without TField declarations."""
        code = "public class Simple { private int x; }"
        ids = extract_thrift_field_ids(code)
        assert len(ids) == 0


class TestParseJavaSourceEdgeCases:
    """Tests for edge cases in parse_java_source."""

    def test_parse_no_class_body(self):
        """Test parsing a file with no class body."""
        java_code = "// Just a comment, no class"
        with tempfile.NamedTemporaryFile(suffix=".java", mode="w", delete=False) as f:
            f.write(java_code)
            f.flush()
            class_name, fields, encoding = parse_java_source(f.name)

        assert fields == []
        assert encoding == ENCODING_BINARY

    def test_parse_empty_class(self):
        """Test parsing a class with no fields."""
        java_code = "public class Empty {}"
        with tempfile.NamedTemporaryFile(suffix=".java", mode="w", delete=False) as f:
            f.write(java_code)
            f.flush()
            class_name, fields, encoding = parse_java_source(f.name)

        assert class_name == "Empty"
        assert len(fields) == 0

    def test_parse_with_package(self):
        """Test parsing respects package declaration."""
        java_code = """
        package com.example.model;
        public class Trade {
            private long tradeId;
        }
        """
        with tempfile.NamedTemporaryFile(suffix=".java", mode="w", delete=False) as f:
            f.write(java_code)
            f.flush()
            class_name, fields, encoding = parse_java_source(f.name)

        assert class_name == "Trade"
        assert len(fields) == 1

    def test_parse_with_generic_field(self):
        """Test parsing fields with generic types."""
        java_code = """
        public class Container {
            private List<String> items;
        }
        """
        with tempfile.NamedTemporaryFile(suffix=".java", mode="w", delete=False) as f:
            f.write(java_code)
            f.flush()
            class_name, fields, encoding = parse_java_source(f.name)

        names = [f.name for f in fields]
        assert "items" in names


class TestJavaFieldsToSchemaEdgeCases:
    """Tests for edge cases in java_fields_to_schema."""

    def test_skips_internal_thrift_fields(self):
        """Test that fields starting with _ are skipped."""
        fields = [
            JavaField(name="orderId", java_type="long"),
            JavaField(name="_fieldName", java_type="String"),
            JavaField(name="__isset_bitfield", java_type="int"),
        ]
        schema = java_fields_to_schema("Order", fields)
        field_names = [f.name for f in schema.messages["Order"].fields]
        assert "orderId" in field_names
        assert "_fieldName" not in field_names
        assert "__isset_bitfield" not in field_names

    def test_object_field_stores_nested_type(self):
        """Test that object fields store their Java type as nested_type."""
        fields = [JavaField(name="header", java_type="HeaderInfo")]
        schema = java_fields_to_schema("Order", fields)
        field_def = schema.messages["Order"].fields[0]
        assert field_def.type == "object"
        assert field_def.nested_type == "HeaderInfo"

    def test_encoding_parameter(self):
        """Test that encoding parameter is set on schema."""
        fields = [JavaField(name="x", java_type="int")]
        schema = java_fields_to_schema("Test", fields, encoding="thrift")
        assert schema.encoding == "thrift"

    def test_encoding_defaults_to_binary(self):
        """Test that encoding defaults to binary when None."""
        fields = [JavaField(name="x", java_type="int")]
        schema = java_fields_to_schema("Test", fields)
        assert schema.encoding == ENCODING_BINARY


class TestJavaTypeMappingEdgeCases:
    """Additional Java type mapping tests."""

    def test_array_types(self):
        """Test array types map to bytes."""
        assert java_type_to_schema_type("int[]") == "bytes"
        assert java_type_to_schema_type("String[]") == "bytes"

    def test_boxed_primitives(self):
        """Test all boxed primitive types."""
        assert java_type_to_schema_type("Byte") == "int8"
        assert java_type_to_schema_type("Short") == "int16"
        assert java_type_to_schema_type("Float") == "float32"
        assert java_type_to_schema_type("Character") == "uint16"
