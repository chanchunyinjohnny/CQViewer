"""Tests for Java parser module."""

import pytest
import struct
import tempfile
from pathlib import Path

from cqviewer.parser.java_parser import (
    parse_java_source, parse_java_class, parse_java_file,
    java_type_to_schema_type, java_fields_to_schema, merge_schemas,
    JavaField,
)
from cqviewer.parser.schema import Schema


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
        schema1 = Schema(
            messages={"Order": None},
            default_message="Order"
        )
        schema2 = Schema(
            messages={"Trade": None},
            default_message=None
        )

        merged = merge_schemas(schema1, schema2)

        assert "Order" in merged.messages
        assert "Trade" in merged.messages
        assert merged.default_message == "Order"

    def test_merge_preserves_first_default(self):
        schema1 = Schema(messages={}, default_message="First")
        schema2 = Schema(messages={}, default_message="Second")

        merged = merge_schemas(schema1, schema2)

        assert merged.default_message == "First"


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
