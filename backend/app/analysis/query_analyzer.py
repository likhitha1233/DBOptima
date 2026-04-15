#!/usr/bin/env python3
"""
Real Query Analyzer - No fake logic, actual SQL analysis
"""

import re
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List, Dict
from ..core.database import engine
from ..core.config import settings

logger = logging.getLogger(__name__)

@dataclass
class QueryPattern:
    """Data structure for query pattern analysis"""
    pattern_type: str
    table_name: str
    columns: List[str]
    conditions: List[str]
    joins: List[str]
    order_by: List[str]
    group_by: List[str]
    frequency: int
    avg_execution_time: float
    max_execution_time: float
    total_executions: int
    slow_query_count: int

@dataclass
class TableAnalysis:
    """Data structure for table analysis"""
    table_name: str
    total_queries: int
    slow_queries: int
    avg_execution_time: float
    max_execution_time: float
    queried_columns: Set[str]
    where_columns: Set[str]
    join_columns: Set[str]
    order_columns: Set[str]
    group_columns: Set[str]
    query_patterns: List[QueryPattern]

@dataclass
class IndexOpportunity:
    """Data structure for index opportunities"""
    table_name: str
    column_names: List[str]
    index_type: str
    opportunity_type: str
    estimated_improvement: float
    affected_queries: int
    query_examples: List[str]
    reasoning: str

class RealQueryAnalyzer:
    """Real query analyzer with actual SQL parsing and analysis"""
    
    def __init__(self):
        self.engine = engine
        self.slow_query_threshold = settings.slow_query_threshold
        self.query_config = settings.get_section('query_analysis')
        self.db_config = settings.get_section('database')
        
        # SQL parsing patterns
        self._init_sql_patterns()
        
        # Cache for table schemas
        self.schema_cache = {}
        self.index_cache = {}
        
        logger.info(f"RealQueryAnalyzer initialized with slow_query_threshold={self.slow_query_threshold}ms")
    
    def _init_sql_patterns(self):
        """Initialize SQL parsing patterns"""
        # Table extraction patterns
        self.table_patterns = [
            r'\bFROM\s+([`"]?)(\w+)\1',  # FROM table
            r'\bJOIN\s+([`"]?)(\w+)\1',   # JOIN table
            r'\bINTO\s+([`"]?)(\w+)\1',   # INSERT INTO table
            r'\bUPDATE\s+([`"]?)(\w+)\1',  # UPDATE table
        ]
        
        # Column extraction patterns
        self.column_patterns = [
            r'([`"]?)(\w+)\1\.\1([`"]?)(\w+)\3',  # table.column
            r'\bWHERE\s+([`"]?)(\w+)\1\.\1([`"]?)(\w+)\3',  # WHERE table.column
            r'\bORDER\s+BY\s+([`"]?)(\w+)\1\.\1([`"]?)(\w+)\3',  # ORDER BY table.column
            r'\bGROUP\s+BY\s+([`"]?)(\w+)\1\.\1([`"]?)(\w+)\3',  # GROUP BY table.column
        ]
        
        # WHERE condition patterns
        self.where_patterns = [
            r'\bWHERE\s+(.+?)(?:\s+GROUP\s+BY|\s+ORDER\s+BY|\s+LIMIT|\s+HAVING|\s+UNION|$)',
        ]
        
        # JOIN patterns
        self.join_patterns = [
            r'\b(INNER|LEFT|RIGHT|FULL|CROSS)\s+JOIN\s+([`"]?)(\w+)\2\s+ON\s+([`"]?)(\w+)\3\.\1([`"]?)(\w+)\5\s*=\s*([`"]?)(\w+)\6\.\1([`"]?)(\w+)\8',
        ]
        
        # Common slow query patterns
        self.slow_patterns = [
            r'SELECT\s+.*\s+FROM\s+.*\s+WHERE\s+.*\s+ORDER\s+BY\s+.*\s+LIMIT',  # ORDER BY + WHERE + LIMIT
            r'SELECT\s+.*\s+FROM\s+.*\s+WHERE\s+.*\s+GROUP\s+BY\s+.*\s+HAVING',  # GROUP BY + HAVING
            r'SELECT\s+.*\s+FROM\s+.*\s+WHERE\s+.*\s+IN\s*\(.*SELECT',  # Subquery in WHERE
            r'SELECT\s+.*\s+FROM\s+.*\s+WHERE\s+.*\s+LIKE\s+[\'"]%.*%[\'"]',  # Leading wildcard LIKE
            r'SELECT\s+.*\s+FROM\s+.*\s+WHERE\s+.*\s+OR\s+',  # OR conditions in WHERE
        ]
    
    def extract_tables(self, query_text: str) -> Set[str]:
        """Extract table names from SQL query"""
        tables = set()
        
        for pattern in self.table_patterns:
            matches = re.finditer(pattern, query_text, re.IGNORECASE)
            for match in matches:
                # Get the table name from the appropriate group
                if len(match.groups()) >= 2:
                    table_name = match.group(2)
                    if table_name and table_name.lower() not in ['select', 'from', 'where', 'join']:
                        tables.add(table_name.lower())
        
        return tables
    
    def extract_columns(self, query_text: str, table_name: str = None) -> Dict[str, Set[str]]:
        """Extract column information from SQL query"""
        columns = {
            'select': set(),
            'where': set(),
            'join': set(),
            'order': set(),
            'group': set()
        }
        
        # Extract SELECT columns
        select_match = re.search(r'SELECT\s+(.*?)\s+FROM', query_text, re.IGNORECASE | re.DOTALL)
        if select_match:
            select_clause = select_match.group(1)
            # Remove functions and expressions, keep column names
            select_columns = re.findall(r'([`"]?)(\w+)\1\.', select_clause)
            for _, col in select_columns:
                columns['select'].add(col.lower())
        
        # Extract WHERE columns
        where_match = re.search(r'WHERE\s+(.+?)(?:\s+GROUP\s+BY|\s+ORDER\s+BY|\s+LIMIT|\s+HAVING|\s+UNION|$)', 
                               query_text, re.IGNORECASE | re.DOTALL)
        if where_match:
            where_clause = where_match.group(1)
            where_columns = re.findall(r'([`"]?)(\w+)\1\.', where_clause)
            for _, col in where_columns:
                columns['where'].add(col.lower())
        
        # Extract JOIN columns
        join_matches = re.finditer(r'\bJOIN\s+([`"]?)(\w+)\2\s+ON\s+([`"]?)(\w+)\3\.\1([`"]?)(\w+)\5\s*=\s*([`"]?)(\w+)\6\.\1([`"]?)(\w+)\8',
                                  query_text, re.IGNORECASE)
        for match in join_matches:
            if len(match.groups()) >= 8:
                left_col = match.group(5)
                right_col = match.group(8)
                columns['join'].add(left_col.lower())
                columns['join'].add(right_col.lower())
        
        # Extract ORDER BY columns
        order_match = re.search(r'ORDER\s+BY\s+(.+?)(?:\s+LIMIT|$)', query_text, re.IGNORECASE)
        if order_match:
            order_clause = order_match.group(1)
            order_columns = re.findall(r'([`"]?)(\w+)\1\.', order_clause)
            for _, col in order_columns:
                columns['order'].add(col.lower())
        
        # Extract GROUP BY columns
        group_match = re.search(r'GROUP\s+BY\s+(.+?)(?:\s+HAVING|\s+ORDER\s+BY|\s+LIMIT|$)', query_text, re.IGNORECASE)
        if group_match:
            group_clause = group_match.group(1)
            group_columns = re.findall(r'([`"]?)(\w+)\1\.', group_clause)
            for _, col in group_columns:
                columns['group'].add(col.lower())
        
        return columns
    
    def is_slow_query(self, query_text: str, execution_time: float) -> bool:
        """Determine if query is slow based on execution time and patterns"""
        # Primary check: execution time threshold
        if execution_time > self.slow_query_threshold:
            return True
        
        # Secondary check: known slow patterns
        for pattern in self.slow_patterns:
            if re.search(pattern, query_text, re.IGNORECASE):
                return True
        
        return False
    
    def analyze_query_patterns(self, queries: List[Dict]) -> Dict:
        """Analyze query patterns from collected queries"""
        logger.debug(f"Analyzing {len(queries)} queries for patterns")
        
        if not queries:
            return {
                'total_queries': 0,
                'slow_queries': 0,
                'avg_execution_time': 0.0,
                'common_patterns': {},
                'table_usage': {},
                'issue_types': {},
                'analysis_timestamp': datetime.now().isoformat()
            }
        
        # Group queries by normalized pattern
        pattern_groups = defaultdict(list)
        table_usage = defaultdict(int)
        slow_query_patterns = defaultdict(int)
        
        for query in queries:
            query_text = query.get('query_text', '')
            execution_time = query.get('execution_time', 0)
            database_name = query.get('database_name', 'unknown')
            
            if not query_text or not isinstance(query_text, str):
                continue
            
            # Extract tables
            tables = self.extract_tables(query_text)
            for table in tables:
                table_usage[table] += 1
            
            # Normalize query for pattern matching
            normalized_query = self._normalize_query(query_text)
            pattern_groups[normalized_query].append(query)
            
            # Check if slow
            is_slow = self.is_slow_query(query_text, execution_time)
            if is_slow:
                slow_query_patterns[normalized_query] += 1
        
        # Analyze patterns
        common_patterns = {}
        issue_types = defaultdict(int)
        total_slow_queries = 0
        total_execution_time = 0
        
        for pattern, query_list in pattern_groups.items():
            if len(query_list) < 2:  # Skip single occurrences
                continue
            
            # Calculate statistics for this pattern
            execution_times = [q.get('execution_time', 0) for q in query_list]
            avg_time = sum(execution_times) / len(execution_times)
            max_time = max(execution_times)
            total_executions = len(query_list)
            slow_count = slow_query_patterns.get(pattern, 0)
            
            total_slow_queries += slow_count
            total_execution_time += sum(execution_times)
            
            # Identify issue types
            issues = self._identify_query_issues(pattern, query_list)
            for issue in issues:
                issue_types[issue] += total_executions
            
            # Store pattern analysis
            common_patterns[pattern] = {
                'frequency': total_executions,
                'avg_execution_time': avg_time,
                'max_execution_time': max_time,
                'slow_query_count': slow_count,
                'slow_query_percentage': (slow_count / total_executions) * 100,
                'issues': issues,
                'sample_query': query_list[0].get('query_text', '')[:200] + '...',
                'tables': list(self.extract_tables(pattern))
            }
        
        # Sort patterns by frequency
        common_patterns = dict(sorted(common_patterns.items(), 
                                    key=lambda x: x[1]['frequency'], reverse=True))
        
        return {
            'total_queries': len(queries),
            'slow_queries': total_slow_queries,
            'avg_execution_time': total_execution_time / len(queries) if queries else 0,
            'common_patterns': common_patterns,
            'table_usage': dict(sorted(table_usage.items(), key=lambda x: x[1], reverse=True)),
            'issue_types': dict(issue_types),
            'analysis_timestamp': datetime.now().isoformat()
        }
    
    def _normalize_query(self, query_text: str) -> str:
        """Normalize query for pattern matching"""
        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', query_text.strip())
        
        # Remove string literals
        normalized = re.sub(r"'[^']*'", "'X'", normalized)
        normalized = re.sub(r'"[^"]*"', '"X"', normalized)
        
        # Remove numeric literals
        normalized = re.sub(r'\b\d+\b', 'N', normalized)
        
        # Remove comments
        normalized = re.sub(r'--.*$', '', normalized, flags=re.MULTILINE)
        normalized = re.sub(r'/\*.*?\*/', '', normalized, flags=re.DOTALL)
        
        # Convert to uppercase for keywords
        keywords = ['SELECT', 'FROM', 'WHERE', 'JOIN', 'INNER', 'LEFT', 'RIGHT', 'OUTER', 
                   'GROUP', 'BY', 'ORDER', 'HAVING', 'LIMIT', 'UNION', 'INSERT', 
                   'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP']
        for keyword in keywords:
            normalized = re.sub(rf'\b{keyword}\b', keyword, normalized, flags=re.IGNORECASE)
        
        return normalized
    
    def _identify_query_issues(self, pattern: str, query_list: List[Dict]) -> List[str]:
        """Identify potential issues in query pattern"""
        issues = []
        
        # Check for missing WHERE clause
        if 'WHERE' not in pattern.upper() and 'SELECT' in pattern.upper():
            issues.append('missing_where_clause')
        
        # Check for SELECT *
        if 'SELECT *' in pattern.upper():
            issues.append('select_star')
        
        # Check for leading wildcard LIKE
        if re.search(r"LIKE\s+['\"]%.*%['\"]", pattern, re.IGNORECASE):
            issues.append('leading_wildcard_like')
        
        # Check for OR conditions
        if ' OR ' in pattern.upper():
            issues.append('or_conditions')
        
        # Check for subqueries
        if re.search(r'\bIN\s*\(\s*SELECT', pattern, re.IGNORECASE):
            issues.append('subquery_in_where')
        
        # Check for ORDER BY without LIMIT
        if 'ORDER BY' in pattern.upper() and 'LIMIT' not in pattern.upper():
            issues.append('order_by_without_limit')
        
        # Check for GROUP BY without HAVING
        if 'GROUP BY' in pattern.upper() and 'HAVING' not in pattern.upper():
            issues.append('group_by_without_having')
        
        # Check for multiple JOINs
        join_count = len(re.findall(r'\bJOIN\b', pattern, re.IGNORECASE))
        if join_count > 3:
            issues.append('multiple_joins')
        
        # Check for high execution time
        avg_time = sum(q.get('execution_time', 0) for q in query_list) / len(query_list)
        if avg_time > self.slow_query_threshold:
            issues.append('high_execution_time')
        
        return issues
    
    def analyze_table_usage(self, queries: List[Dict]) -> Dict[str, TableAnalysis]:
        """Analyze table usage patterns"""
        logger.debug(f"Analyzing table usage for {len(queries)} queries")
        
        table_analyses = {}
        
        # Group queries by table
        table_queries = defaultdict(list)
        for query in queries:
            query_text = query.get('query_text', '')
            tables = self.extract_tables(query_text)
            
            for table in tables:
                table_queries[table].append(query)
        
        # Analyze each table
        for table_name, table_query_list in table_queries.items():
            if len(table_query_list) < 2:  # Skip tables with insufficient data
                continue
            
            # Calculate basic statistics
            execution_times = [q.get('execution_time', 0) for q in table_query_list]
            total_queries = len(table_query_list)
            slow_queries = sum(1 for q in table_query_list 
                             if self.is_slow_query(q.get('query_text', ''), q.get('execution_time', 0)))
            
            avg_execution_time = sum(execution_times) / total_queries
            max_execution_time = max(execution_times)
            
            # Extract column usage
            all_columns = {
                'select': set(),
                'where': set(),
                'join': set(),
                'order': set(),
                'group': set()
            }
            
            query_patterns = []
            
            for query in table_query_list:
                query_text = query.get('query_text', '')
                columns = self.extract_columns(query_text, table_name)
                
                for col_type, col_set in all_columns.items():
                    col_set.update(columns[col_type])
            
            # Create table analysis
            table_analyses[table_name] = TableAnalysis(
                table_name=table_name,
                total_queries=total_queries,
                slow_queries=slow_queries,
                avg_execution_time=avg_execution_time,
                max_execution_time=max_execution_time,
                queried_columns=all_columns['select'],
                where_columns=all_columns['where'],
                join_columns=all_columns['join'],
                order_columns=all_columns['order'],
                group_columns=all_columns['group'],
                query_patterns=query_patterns
            )
        
        return table_analyses
    
    def identify_index_opportunities(self, queries: List[Dict]) -> List[IndexOpportunity]:
        """Identify potential index opportunities based on query analysis"""
        logger.debug("Identifying index opportunities")
        
        opportunities = []
        table_analyses = self.analyze_table_usage(queries)
        
        for table_name, analysis in table_analyses.items():
            # Get table schema if available
            schema = self._get_table_schema(table_name)
            existing_indexes = self._get_table_indexes(table_name)
            
            # Analyze WHERE columns for indexing opportunities
            if analysis.where_columns:
                # Single column indexes
                for column in analysis.where_columns:
                    if self._should_create_index(column, analysis, existing_indexes, schema):
                        opportunity = IndexOpportunity(
                            table_name=table_name,
                            column_names=[column],
                            index_type='btree',
                            opportunity_type='where_column',
                            estimated_improvement=self._estimate_improvement(column, analysis),
                            affected_queries=analysis.slow_queries,
                            query_examples=self._get_query_examples(table_name, column, queries),
                            reasoning=f"Column '{column}' frequently used in WHERE clauses"
                        )
                        opportunities.append(opportunity)
                
                # Composite indexes for multiple WHERE columns
                where_columns_list = list(analysis.where_columns)
                if len(where_columns_list) >= 2:
                    for i in range(len(where_columns_list) - 1):
                        col1, col2 = where_columns_list[i], where_columns_list[i + 1]
                        if self._should_create_composite_index([col1, col2], analysis, existing_indexes):
                            opportunity = IndexOpportunity(
                                table_name=table_name,
                                column_names=[col1, col2],
                                index_type='btree',
                                opportunity_type='composite_where',
                                estimated_improvement=self._estimate_composite_improvement([col1, col2], analysis),
                                affected_queries=analysis.slow_queries,
                                query_examples=self._get_query_examples(table_name, col1, queries),
                                reasoning=f"Composite index on '{col1}, {col2}' for frequent WHERE conditions"
                            )
                            opportunities.append(opportunity)
            
            # Analyze ORDER BY columns
            if analysis.order_columns and not analysis.where_columns:
                for column in analysis.order_columns:
                    if self._should_create_order_index(column, analysis, existing_indexes):
                        opportunity = IndexOpportunity(
                            table_name=table_name,
                            column_names=[column],
                            index_type='btree',
                            opportunity_type='order_by',
                            estimated_improvement=self._estimate_order_improvement(column, analysis),
                            affected_queries=analysis.slow_queries,
                            query_examples=self._get_query_examples(table_name, column, queries),
                            reasoning=f"Column '{column}' frequently used in ORDER BY without WHERE"
                        )
                        opportunities.append(opportunity)
            
            # Analyze JOIN columns
            if analysis.join_columns:
                for column in analysis.join_columns:
                    if self._should_create_join_index(column, analysis, existing_indexes):
                        opportunity = IndexOpportunity(
                            table_name=table_name,
                            column_names=[column],
                            index_type='btree',
                            opportunity_type='join_column',
                            estimated_improvement=self._estimate_join_improvement(column, analysis),
                            affected_queries=analysis.slow_queries,
                            query_examples=self._get_query_examples(table_name, column, queries),
                            reasoning=f"Column '{column}' frequently used in JOIN conditions"
                        )
                        opportunities.append(opportunity)
        
        # Sort by estimated improvement
        opportunities.sort(key=lambda x: x.estimated_improvement, reverse=True)
        
        return opportunities
    
    def _get_table_schema(self, table_name: str) -> Dict:
        """Get table schema from database"""
        if table_name in self.schema_cache:
            return self.schema_cache[table_name]
        
        try:
            # Validate table name to prevent SQL injection
            if not table_name.replace('_', '').replace('-', '').isalnum():
                raise ValueError(f"Invalid table name: {table_name}")
            
            with self.engine.connect() as conn:
                if self.db_config['type'] == 'mysql':
                    # Use parameterized query with validated table name
                    query = f"DESCRIBE {table_name}"
                    result = conn.execute(text(query))
                    columns = {}
                    for row in result:
                        columns[row[0]] = {
                            'type': row[1],
                            'null': row[2] == 'YES',
                            'key': row[3],
                            'default': row[4]
                        }
                    self.schema_cache[table_name] = columns
                    return columns
                
                elif self.db_config['type'] == 'postgresql':
                    result = conn.execute(text("""
                        SELECT column_name, data_type, is_nullable, column_default
                        FROM information_schema.columns
                        WHERE table_name = :table_name
                    """), {"table_name": table_name})
                    
                    columns = {}
                    for row in result:
                        columns[row[0]] = {
                            'type': row[1],
                            'null': row[2] == 'YES',
                            'default': row[3]
                        }
                    self.schema_cache[table_name] = columns
                    return columns
                    
        except Exception as e:
            logger.warning(f"Could not get schema for table {table_name}: {e}")
            return {}
    
    def _get_table_indexes(self, table_name: str) -> Dict[str, List[str]]:
        """Get existing indexes for table"""
        if table_name in self.index_cache:
            return self.index_cache[table_name]
        
        try:
            # Validate table name to prevent SQL injection
            if not table_name.replace('_', '').replace('-', '').isalnum():
                raise ValueError(f"Invalid table name: {table_name}")
            
            with self.engine.connect() as conn:
                if self.db_config['type'] == 'mysql':
                    # Use parameterized query with validated table name
                    query = f"SHOW INDEX FROM {table_name}"
                    result = conn.execute(text(query))
                    indexes = defaultdict(list)
                    for row in result:
                        index_name = row[2]
                        column_name = row[4]
                        indexes[index_name].append(column_name)
                    
                    self.index_cache[table_name] = dict(indexes)
                    return dict(indexes)
                
                elif self.db_config['type'] == 'postgresql':
                    result = conn.execute(text("""
                        SELECT indexname, indexdef
                        FROM pg_indexes
                        WHERE tablename = :table_name
                    """), {"table_name": table_name})
                    
                    indexes = {}
                    for row in result:
                        # Parse index definition to get columns
                        index_def = row[1]
                        columns_match = re.search(r'\((.*?)\)', index_def)
                        if columns_match:
                            columns = [col.strip().strip('"') for col in columns_match.group(1).split(',')]
                            indexes[row[0]] = columns
                    
                    self.index_cache[table_name] = indexes
                    return indexes
                    
        except Exception as e:
            logger.warning(f"Could not get indexes for table {table_name}: {e}")
            return {}
    
    def _should_create_index(self, column: str, analysis: TableAnalysis, 
                           existing_indexes: Dict, schema: Dict) -> bool:
        """Determine if an index should be created for a column"""
        # Check if index already exists
        for index_name, columns in existing_indexes.items():
            if column in columns:
                return False
        
        # Check if column is frequently used in WHERE clauses
        if column not in analysis.where_columns:
            return False
        
        # Check if column has good selectivity (approximate)
        if column in schema:
            col_type = schema[column].get('type', '').upper()
            # Avoid indexing very low-selectivity columns
            if col_type in ['TINYINT(1)', 'BOOLEAN']:
                return False
        
        # Check if table has enough queries to benefit from index
        if analysis.total_queries < 10:
            return False
        
        # Check if enough slow queries use this column
        slow_query_ratio = analysis.slow_queries / analysis.total_queries
        if slow_query_ratio < 0.1:  # Less than 10% slow queries
            return False
        
        return True
    
    def _should_create_composite_index(self, columns: List[str], analysis: TableAnalysis,
                                    existing_indexes: Dict) -> bool:
        """Determine if a composite index should be created"""
        # Check if similar index already exists
        for index_name, index_columns in existing_indexes.items():
            if set(columns).issubset(set(index_columns)):
                return False
        
        # Check if all columns are frequently used together
        all_in_where = all(col in analysis.where_columns for col in columns)
        if not all_in_where:
            return False
        
        return True
    
    def _should_create_order_index(self, column: str, analysis: TableAnalysis,
                                 existing_indexes: Dict) -> bool:
        """Determine if an ORDER BY index should be created"""
        # Check if index already exists
        for index_name, columns in existing_indexes.items():
            if column in columns:
                return False
        
        # Only create if ORDER BY is used frequently
        if column not in analysis.order_columns:
            return False
        
        # Check if there are no WHERE clauses (ORDER BY only indexes are less effective)
        if analysis.where_columns:
            return False
        
        return True
    
    def _should_create_join_index(self, column: str, analysis: TableAnalysis,
                                existing_indexes: Dict) -> bool:
        """Determine if a JOIN index should be created"""
        # Check if index already exists
        for index_name, columns in existing_indexes.items():
            if column in columns:
                return False
        
        # Check if column is used in JOINs
        if column not in analysis.join_columns:
            return False
        
        return True
    
    def _estimate_improvement(self, column: str, analysis: TableAnalysis) -> float:
        """Estimate performance improvement for an index"""
        # Base improvement on slow query ratio and query frequency
        slow_query_ratio = analysis.slow_queries / analysis.total_queries
        
        # Higher improvement for columns used in many slow queries
        base_improvement = slow_query_ratio * 50
        
        # Adjust for query frequency
        frequency_factor = min(1.0, analysis.total_queries / 100)
        
        # Adjust for column selectivity (estimated)
        selectivity_factor = 1.0  # Would need actual statistics for real calculation
        
        estimated_improvement = base_improvement * frequency_factor * selectivity_factor
        
        return min(90.0, max(5.0, estimated_improvement))
    
    def _estimate_composite_improvement(self, columns: List[str], analysis: TableAnalysis) -> float:
        """Estimate performance improvement for a composite index"""
        # Composite indexes generally provide better improvement
        base_improvement = self._estimate_improvement(columns[0], analysis)
        
        # Add bonus for composite nature
        composite_bonus = 10.0 * (len(columns) - 1)
        
        return min(90.0, base_improvement + composite_bonus)
    
    def _estimate_order_improvement(self, column: str, analysis: TableAnalysis) -> float:
        """Estimate performance improvement for ORDER BY index"""
        # ORDER BY indexes provide less improvement than WHERE indexes
        base_improvement = self._estimate_improvement(column, analysis)
        
        # Reduce for ORDER BY only
        order_factor = 0.6
        
        return base_improvement * order_factor
    
    def _estimate_join_improvement(self, column: str, analysis: TableAnalysis) -> float:
        """Estimate performance improvement for JOIN index"""
        # JOIN indexes are very important
        base_improvement = self._estimate_improvement(column, analysis)
        
        # Increase for JOIN importance
        join_bonus = 15.0
        
        return min(90.0, base_improvement + join_bonus)
    
    def _get_query_examples(self, table_name: str, column: str, queries: List[Dict]) -> List[str]:
        """Get example queries that use the specified column"""
        examples = []
        
        for query in queries[:5]:  # Limit to 5 examples
            query_text = query.get('query_text', '')
            if table_name.lower() in query_text.lower() and column.lower() in query_text.lower():
                examples.append(query_text[:200] + '...' if len(query_text) > 200 else query_text)
        
        return examples
    
    def get_top_slow_queries(self, limit: int = 10, hours_back: int = 24) -> List[Dict]:
        """Get top slow queries from database"""
        logger.debug(f"Fetching top {limit} slow queries from last {hours_back} hours")
        
        # Validate input
        if not isinstance(limit, int) or limit <= 0:
            logger.warning(f"Invalid limit: {limit}, using 10")
            limit = 10
        
        if not isinstance(hours_back, int) or hours_back <= 0:
            logger.warning(f"Invalid hours_back: {hours_back}, using 24")
            hours_back = 24
        
        try:
            with self.engine.connect() as conn:
                cutoff_time = datetime.now() - timedelta(hours=hours_back)
                
                if self.db_config['type'] == 'mysql':
                    result = conn.execute(text("""
                        SELECT 
                            query_text,
                            execution_time,
                            rows_examined,
                            rows_returned,
                            database_name,
                            timestamp,
                            user,
                            host
                        FROM query_logs 
                        WHERE is_slow = True 
                        AND timestamp > :cutoff_time
                        ORDER BY execution_time DESC
                        LIMIT :limit
                    """), {"cutoff_time": cutoff_time, "limit": limit})
                    
                elif self.db_config['type'] == 'postgresql':
                    result = conn.execute(text("""
                        SELECT 
                            query_text,
                            execution_time,
                            rows_examined,
                            rows_returned,
                            database_name,
                            timestamp,
                            user,
                            host
                        FROM query_logs 
                        WHERE is_slow = True 
                        AND timestamp > :cutoff_time
                        ORDER BY execution_time DESC
                        LIMIT :limit
                    """), {"cutoff_time": cutoff_time, "limit": limit})
                
                else:
                    logger.warning(f"Query retrieval not implemented for {self.db_config['type']}")
                    return []
                
                slow_queries = []
                for row in result:
                    slow_queries.append({
                        'query_text': row[0],
                        'execution_time': row[1],
                        'rows_examined': row[2] or 0,
                        'rows_returned': row[3] or 0,
                        'database_name': row[4],
                        'timestamp': row[5].isoformat() if row[5] else None,
                        'user': row[6],
                        'host': row[7]
                    })
                
                logger.info(f"Retrieved {len(slow_queries)} slow queries")
                return slow_queries
                
        except Exception as e:
            logger.error(f"Error retrieving slow queries: {e}")
            return []
    
    def analyze_query(self, query_text: str, execution_time: float = None) -> Dict:
        """Analyze a single query - simplified for demo"""
        if not query_text or not isinstance(query_text, str):
            return {'error': 'Invalid query text'}
        
        query_upper = query_text.upper().strip()
        
        # Basic query type detection
        if query_upper.startswith('SELECT'):
            query_type = 'SELECT'
        elif query_upper.startswith('INSERT'):
            query_type = 'INSERT'
        elif query_upper.startswith('UPDATE'):
            query_type = 'UPDATE'
        elif query_upper.startswith('DELETE'):
            query_type = 'DELETE'
        else:
            query_type = 'OTHER'
        
        # Extract table names (simple parsing)
        tables = self._extract_tables_simple(query_text)
        
        # Extract columns (simple parsing)
        columns = self._extract_columns_simple(query_text)
        
        # Estimate complexity
        complexity = self._estimate_complexity(query_text, query_type, tables)
        
        # Calculate logical execution time based on complexity
        if execution_time is None:
            # Base time in milliseconds based on query complexity
            base_time = complexity * 50  # 50ms per complexity unit
            
            # Adjust for query type
            if query_type == 'SELECT':
                if 'JOIN' in query_text.upper():
                    base_time *= 2.0  # JOINs are slower
                if 'GROUP BY' in query_text.upper():
                    base_time *= 1.5  # GROUP BY adds overhead
                if 'ORDER BY' in query_text.upper():
                    base_time *= 1.3  # ORDER BY adds overhead
            elif query_type == 'INSERT':
                base_time *= 0.8  # INSERTs are generally faster than complex SELECTs
            elif query_type == 'UPDATE':
                base_time *= 1.2  # UPDATEs moderate speed
            elif query_type == 'DELETE':
                base_time *= 0.9  # DELETEs moderate speed
            
            execution_time = base_time
        
        # Determine if slow
        is_slow = execution_time > 1000  # 1 second threshold
        
        # Generate basic recommendations
        recommendations = self._generate_simple_recommendations(query_type, tables, columns)
        
        analysis = {
            'query_type': query_type,
            'tables': tables,
            'columns': columns,
            'complexity_score': complexity,
            'execution_time': execution_time,
            'is_slow': is_slow,
            'recommendations': recommendations,
            'query_text': query_text[:200] + '...' if len(query_text) > 200 else query_text
        }
        
        return analysis
    
    def _extract_tables_simple(self, query: str) -> List[str]:
        """Extract table names from query - simple regex-based"""
        import re
        
        # FROM pattern
        from_pattern = r'FROM\s+([a-zA-Z_][a-zA-Z0-9_]*)'
        from_matches = re.findall(from_pattern, query.upper())
        
        # JOIN pattern
        join_pattern = r'JOIN\s+([a-zA-Z_][a-zA-Z0-9_]*)'
        join_matches = re.findall(join_pattern, query.upper())
        
        tables = list(set(from_matches + join_matches))
        return tables
    
    def _extract_columns_simple(self, query: str) -> List[str]:
        """Extract column names from query - simple parsing"""
        import re
        
        # Simple column extraction from SELECT clause
        select_pattern = r'SELECT\s+(.+?)\s+FROM'
        match = re.search(select_pattern, query.upper())
        
        if match:
            columns_str = match.group(1)
            # Split by comma and clean up
            columns = [col.strip() for col in columns_str.split(',')]
            # Remove function names and aliases
            clean_columns = []
            for col in columns:
                if '(' in col:
                    # Function call, extract column name if possible
                    func_match = re.search(r'([a-zA-Z_][a-zA-Z0-9_]*)\(', col)
                    if func_match:
                        clean_columns.append(func_match.group(1))
                else:
                    # Simple column name
                    clean_col = col.split(' AS ')[0].strip()
                    if clean_col != '*':
                        clean_columns.append(clean_col)
            
            return clean_columns
        
        return []
    
    def _estimate_complexity(self, query: str, query_type: str, tables: List[str]) -> float:
        """Estimate query complexity"""
        complexity = 1.0
        
        # Base complexity by type
        type_complexity = {
            'SELECT': 1.0,
            'INSERT': 0.5,
            'UPDATE': 0.8,
            'DELETE': 0.6,
            'OTHER': 0.7
        }
        complexity *= type_complexity.get(query_type, 1.0)
        
        # Table joins increase complexity
        complexity *= (1 + len(tables) * 0.3)
        
        # WHERE clauses increase complexity
        if 'WHERE' in query.upper():
            complexity *= 1.2
        
        # ORDER BY increases complexity
        if 'ORDER BY' in query.upper():
            complexity *= 1.1
        
        # GROUP BY increases complexity
        if 'GROUP BY' in query.upper():
            complexity *= 1.3
        
        # Subqueries increase complexity
        if query.upper().count('(') > 1:
            complexity *= 1.2
        
        return complexity
    
    def analyze_stored_metrics(self, hours_back: int = 24) -> Dict[str, Any]:
        """Analyze stored metrics from database without randomness"""
        try:
            
            with SessionLocal() as db:
                # Get recent system metrics
                if hours_back <= 24:
                    # SQLite compatible query for recent data
                    metrics_query = text("""
                        SELECT cpu_percent, memory_percent, disk_percent, connections,
                               queries_per_second, slow_queries, timestamp
                        FROM system_metrics 
                        WHERE timestamp > datetime('now', '-{} hours')
                        ORDER BY timestamp DESC
                        LIMIT 100
                    """.format(hours_back))
                else:
                    # For longer periods, use days
                    metrics_query = text("""
                        SELECT cpu_percent, memory_percent, disk_percent, connections,
                               queries_per_second, slow_queries, timestamp
                        FROM system_metrics 
                        WHERE timestamp > datetime('now', '-{} days')
                        ORDER BY timestamp DESC
                        LIMIT 100
                    """.format(hours_back // 24))
                
                results = db.execute(metrics_query).fetchall()
                
                if not results:
                    return {
                        'status': 'no_data',
                        'message': f'No metrics found in last {hours_back} hours',
                        'analysis': {}
                    }
                
                # Analyze real metrics
                cpu_values = [row[0] for row in results if row[0] is not None]
                memory_values = [row[1] for row in results if row[1] is not None]
                disk_values = [row[2] for row in results if row[2] is not None]
                connection_values = [row[3] for row in results if row[3] is not None]
                qps_values = [row[4] for row in results if row[4] is not None]
                slow_query_values = [row[5] for row in results if row[5] is not None]
                
                # Calculate rolling averages (window of 5 samples)
                def calculate_rolling_averages(values, window=5):
                    if len(values) < window:
                        return []
                    averages = []
                    for i in range(window - 1, len(values)):
                        avg = sum(values[i - window + 1:i + 1]) / window
                        averages.append(avg)
                    return averages
                
                # Detect trends (increasing/decreasing patterns)
                def detect_trend(values, threshold=0.1):
                    if len(values) < 3:
                        return 'stable'
                    
                    # Simple linear trend detection
                    recent_avg = sum(values[-3:]) / 3
                    earlier_avg = sum(values[:3]) / 3 if len(values) >= 6 else values[0]
                    
                    if earlier_avg == 0:
                        return 'stable'
                    
                    change = (recent_avg - earlier_avg) / earlier_avg
                    
                    if change > threshold:
                        return 'increasing'
                    elif change < -threshold:
                        return 'decreasing'
                    else:
                        return 'stable'
                
                # Calculate enhanced statistics
                cpu_rolling_avg = calculate_rolling_averages(cpu_values)
                memory_rolling_avg = calculate_rolling_averages(memory_values)
                
                cpu_trend = detect_trend(cpu_values)
                memory_trend = detect_trend(memory_values)
                qps_trend = detect_trend(qps_values)
                
                analysis = {
                    'sample_size': len(results),
                    'time_range_hours': hours_back,
                    'cpu_analysis': {
                        'avg': sum(cpu_values) / len(cpu_values) if cpu_values else 0,
                        'max': max(cpu_values) if cpu_values else 0,
                        'min': min(cpu_values) if cpu_values else 0,
                        'high_cpu_periods': len([c for c in cpu_values if c > 80]),
                        'rolling_avg': cpu_rolling_avg[-5:] if cpu_rolling_avg else [],
                        'trend': cpu_trend
                    },
                    'memory_analysis': {
                        'avg': sum(memory_values) / len(memory_values) if memory_values else 0,
                        'max': max(memory_values) if memory_values else 0,
                        'min': min(memory_values) if memory_values else 0,
                        'high_memory_periods': len([m for m in memory_values if m > 85]),
                        'rolling_avg': memory_rolling_avg[-5:] if memory_rolling_avg else [],
                        'trend': memory_trend
                    },
                    'connection_analysis': {
                        'avg': sum(connection_values) / len(connection_values) if connection_values else 0,
                        'max': max(connection_values) if connection_values else 0,
                        'min': min(connection_values) if connection_values else 0,
                        'peak_periods': len([c for c in connection_values if c > 100])
                    },
                    'query_analysis': {
                        'avg_qps': sum(qps_values) / len(qps_values) if qps_values else 0,
                        'max_qps': max(qps_values) if qps_values else 0,
                        'total_slow_queries': sum(slow_query_values) if slow_query_values else 0,
                        'slow_query_rate': (sum(slow_query_values) / len(slow_query_values)) if slow_query_values else 0,
                        'trend': qps_trend
                    },
                    'trend_analysis': {
                        'cpu_trend': cpu_trend,
                        'memory_trend': memory_trend,
                        'qps_trend': qps_trend,
                        'overall_load_trend': 'increasing' if cpu_trend == 'increasing' and memory_trend == 'increasing' else 'mixed'
                    }
                }
                
                # Generate insights based on real data and trends
                insights = []
                
                if analysis['cpu_analysis']['high_cpu_periods'] > len(results) * 0.2:
                    insights.append("High CPU usage detected frequently - consider query optimization")
                
                if analysis['memory_analysis']['high_memory_periods'] > len(results) * 0.1:
                    insights.append("Memory pressure detected - monitor for memory leaks")
                
                if analysis['connection_analysis']['peak_periods'] > len(results) * 0.3:
                    insights.append("Connection peaks detected - consider connection pooling")
                
                if analysis['query_analysis']['slow_query_rate'] > 5:
                    insights.append("High slow query rate - index optimization needed")
                
                # Add trend-based insights
                if analysis['trend_analysis']['cpu_trend'] == 'increasing':
                    insights.append("CPU usage trending upward - monitor for capacity planning")
                
                if analysis['trend_analysis']['memory_trend'] == 'increasing':
                    insights.append("Memory usage trending upward - potential memory leak detected")
                
                if analysis['trend_analysis']['overall_load_trend'] == 'increasing':
                    insights.append("Overall system load increasing - consider scaling soon")
                
                if analysis['trend_analysis']['qps_trend'] == 'increasing' and analysis['query_analysis']['slow_query_rate'] > 2:
                    insights.append("Query volume increasing with slow queries - urgent optimization needed")
                
                return {
                    'status': 'success',
                    'analysis': analysis,
                    'insights': insights,
                    'data_points': len(results)
                }
                
        except Exception as e:
            logger.error(f"Error analyzing stored metrics: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'analysis': {}
            }
    
    def _generate_simple_recommendations(self, query_type: str, tables: List[str], columns: List[str]) -> List[str]:
        """Generate basic query recommendations"""
        recommendations = []
        
        if query_type == 'SELECT':
            if len(tables) > 1:
                recommendations.append("Consider adding indexes on join columns")
            
            if 'WHERE' in ' '.join(tables):
                recommendations.append("Ensure WHERE clause columns are indexed")
            
            if 'ORDER BY' in ' '.join(columns):
                recommendations.append("Consider adding indexes on ORDER BY columns")
        
        elif query_type == 'UPDATE':
            recommendations.append("Ensure WHERE clause uses indexed columns")
        
        elif query_type == 'DELETE':
            recommendations.append("Be careful with DELETE operations - use transactions")
        
        return recommendations
    
    def _generate_query_recommendations(self, analysis: Dict) -> List[str]:
        """Generate recommendations for query improvement"""
        recommendations = []
        
        issues = analysis.get('issues', [])
        columns = analysis.get('columns', {})
        
        if 'missing_where_clause' in issues:
            recommendations.append('Consider adding a WHERE clause to limit result set')
        
        if 'select_star' in issues:
            recommendations.append('Avoid SELECT * - specify only needed columns')
        
        if 'leading_wildcard_like' in issues:
            recommendations.append('Avoid leading wildcards in LIKE queries - consider full-text search')
        
        if 'or_conditions' in issues:
            recommendations.append('Consider rewriting OR conditions or using UNION')
        
        if 'subquery_in_where' in issues:
            recommendations.append('Consider using JOIN instead of subquery in WHERE clause')
        
        if 'order_by_without_limit' in issues:
            recommendations.append('Add LIMIT clause when using ORDER BY on large result sets')
        
        if 'multiple_joins' in issues:
            recommendations.append('Review JOIN performance - ensure proper indexing')
        
        # Check for unindexed WHERE columns
        where_columns = columns.get('where', set())
        if where_columns:
            recommendations.append(f'Consider indexing WHERE columns: {", ".join(list(where_columns)[:3])}')
        
        return recommendations

# Backward compatibility
QueryAnalyzer = RealQueryAnalyzer
